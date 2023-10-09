from django.contrib.auth.hashers import make_password, check_password
from django.db import IntegrityError
from django_rest_passwordreset.serializers import PasswordTokenSerializer
from rest_framework import serializers
from rest_framework.exceptions import ValidationError
from rest_framework.validators import UniqueTogetherValidator
from .email_sender import send_confirmation_email
from .models import User, Shop, Category, Product, Contact, \
    ProductParameter, ProductInfo, SellerOrderItem, SellerOrder, Parameter, ShopCategory, BuyerOrder, ValueOfParameter
from .app_choices import SellerOrderState, PartnerState
from django.contrib.auth.password_validation import validate_password


class ContactSerializer(serializers.ModelSerializer):
    user = serializers.HiddenField(default=serializers.CurrentUserDefault())

    class Meta:
        model = Contact
        fields = ('id', 'city', 'street', 'house', 'structure', 'building', 'apartment', 'user', 'phone')
        read_only_fields = ('id',)
        extra_kwargs = {
            'user': {'write_only': True}
        }

        validators = [
            UniqueTogetherValidator(
                queryset=model.objects.all(),
                fields=('user',
                        'city',
                        'street',
                        'house',
                        'structure',
                        'building',
                        'apartment',
                        'phone'),
                message='This contact is already exists.'
            )
        ]

    def update(self, instance, validated_data):
        if instance.seller_orders.exists():
            raise ValidationError({'error': 'can not to change contact. If you want, you can create a new'})
        return super().update(instance, validated_data)


class PasswordMatchValidateMixin:
    def validate(self, attrs):
        password = attrs.get('password')
        confirmed_password = attrs.pop('password2')
        if password != confirmed_password:
            raise serializers.ValidationError({'password': 'Password mismatch'})
        return attrs


class AuthenticateSerializer(serializers.Serializer):
    email = serializers.EmailField(write_only=True)
    password = serializers.CharField(write_only=True)


class UserSerializer(serializers.ModelSerializer, PasswordMatchValidateMixin):
    current_password = serializers.CharField(required=False, write_only=True)
    password2 = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('id', 'username', 'current_password', 'password', 'password2', 'email', 'first_name', 'last_name')
        extra_kwargs = {'password': {'write_only': True}}
        read_only_fields = ('id', )

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate(self, attrs):
        if 'password' in attrs or 'password2' in attrs:
            return PasswordMatchValidateMixin.validate(self, attrs)
        return attrs

    def create(self, validated_data):
        validated_data['password'] = make_password(validated_data['password'])
        user = super().create(validated_data)
        user.send_email_confirmation(self.context['request'])
        return user

    def update(self, instance, validated_data):
        if 'email' in validated_data:
            del validated_data['email']

        if 'password' in validated_data:
            current_password = validated_data.pop('current_password')
            if current_password == validated_data.get('password'):
                raise serializers.ValidationError('Current password and new password can not be same')
            if not check_password(current_password, instance.password):
                raise serializers.ValidationError('Incorrect current password')
            validated_data['password'] = make_password(validated_data['password'])
            instance.update_auth_token()
        return super().update(instance, validated_data)


class ShopSerializer(serializers.ModelSerializer):
    class Meta:
        model = Shop
        fields = ('id', 'name', 'url', 'email')
        read_only_fields = ('id',)

    def validate(self, data):
        request = self.context['request']
        user = request.auth.user
        if request.method == 'POST' and Shop.objects.filter(owner=user).first():
            raise ValidationError({'error': 'you already have a shop'})
        return data

    def create(self, validated_data):
        user = self.context['request'].auth.user
        validated_data['owner'] = user
        return super().create(validated_data)


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name',)
        read_only_fields = ('id',)


class ProductSerializer(serializers.ModelSerializer):
    name = serializers.CharField()

    class Meta:
        model = Product
        fields = ('name', )


class ProductParameterSerializer(serializers.ModelSerializer):
    parameter = serializers.CharField()
    value = serializers.CharField()

    class Meta:
        model = ProductParameter
        fields = ('parameter', 'value',)


class ProductInfoBaseSerializer(serializers.ModelSerializer):
    product = ProductSerializer(read_only=True)
    product_parameters = ProductParameterSerializer(read_only=True, many=True)

    class Meta:
        model = ProductInfo


class ProductInfoSerializer(ProductInfoBaseSerializer):
    category = BuyerCategorySerializer(read_only=True)
    shop = ShopSerializer(read_only=True)

    class Meta(ProductInfoBaseSerializer.Meta):
        fields = ('id', 'category', 'product', 'product_parameters', 'shop', 'quantity', 'price', 'price_rrc',)
        read_only_fields = ('id',)


class ProductInfoForOrderSerializer(ProductInfoSerializer):
    class Meta(ProductInfoBaseSerializer.Meta):
        fields = ('id', 'category', 'product', 'product_parameters', 'price', 'price_rrc',)


class PartnerCategorySerializer(serializers.ModelSerializer):
    name = serializers.CharField(max_length=50)
    external_id = serializers.IntegerField(min_value=1)

    class Meta:
        model = ShopCategory
        fields = ('id', 'name', 'external_id')
        read_only_fields = ('id',)

    def to_representation(self, instance):
        data = super().to_representation(instance)
        data['id'] = instance.category.id
        return data


class BuyerCategorySerializer(PartnerCategorySerializer):

    class Meta(PartnerCategorySerializer.Meta):
        fields = ('id', 'name', )


class PartnerProductInfoBriefSerializer(ProductInfoBaseSerializer):
    class Meta(ProductInfoBaseSerializer.Meta):
        fields = ('product_parameters', 'quantity', 'price', 'price_rrc',)


class PartnerProductInfoSerializer(ProductInfoBaseSerializer):
    product = ProductSerializer()
    product_parameters = ProductParameterSerializer(many=True)
    category = PartnerCategorySerializer()

    class Meta(ProductInfoBaseSerializer.Meta):
        fields = ('id', 'external_id', 'category', 'product', 'product_parameters', 'quantity', 'price', 'price_rrc',)

    @property
    def is_http_method_update(self):
        return self.context['request'].method in {'PATCH', 'PUT'}

    def validate_external_id(self, value):
        if self.is_http_method_update:
            raise ValidationError(f'changing of external_id not allowed')
        elif self.context['view'].action != 'create_catalogue' \
                and self.shop.product_infos.filter(external_id=value).exists():

            raise ValidationError(f'product with external_id {value} is already exists in your shop')
        return value

    def validate(self, attrs):
        unupdatable_fields = {'product', 'category'}
        if self.is_http_method_update and unupdatable_fields & attrs.keys():
            raise ValidationError({'error': f'changing of fields {", ".join(unupdatable_fields)} not allowed'})
        return attrs

    def create(self, validated_data):
        product_data = validated_data.pop('product')
        category_data = validated_data.pop('category')
        category_external_id = category_data['external_id']
        category_name = category_data['name']

        category_object, category_created = Category.objects.get_or_create(name=category_name)

        try:
            shop_category, shop_category_created = \
                self.shop.categories.get_or_create(category=category_object,
                                                   defaults={'external_id': category_external_id})

        except IntegrityError:
            raise ValidationError({'category_external_id': f'category with external_id '
                                                           f'{category_external_id} already exists'})

        product_object, product_created = Product.objects.get_or_create(name=product_data['name'])

        product_parameters = validated_data.pop('product_parameters')

        product_info = ProductInfo.objects.create(product=product_object,
                                                  shop=self.shop,
                                                  category=shop_category,
                                                  **validated_data)

        self._add_parameters(product_info, product_parameters)
        return product_info

    def update(self, instance, validated_data):

        """
        The method updates: 'product_parameters', 'quantity', 'price', 'price_rrc'.
        If the field is specified 'product_parameters',
        then it is completely replaced by the provided one (PUT).
        """

        product_parameters = validated_data.pop('product_parameters', None)

        if product_parameters is not None:
            self._add_parameters(instance, product_parameters, replace_old=True)

        return super().update(instance, validated_data)

    def update_or_create(self, validated_data: dict):
        instance = self.shop.product_infos.filter(external_id=validated_data['external_id'])\
            .prefetch_related('product_parameters',
                              'product_parameters__parameter',
                              'product_parameters__value').first()
        if instance:
            sort_key = lambda x: x['parameter']
            instance_data = PartnerProductInfoBriefSerializer(instance).data
            product_parameters_old = instance_data.pop('product_parameters')
            product_parameters_old.sort(key=sort_key)
            product_parameters_new = validated_data['product_parameters']
            fields_to_update = {key: validated_data[key]
                                for key, value in instance_data.items() if value != validated_data[key]}
            if product_parameters_old != sorted(product_parameters_new, key=sort_key):
                fields_to_update['product_parameters'] = product_parameters_new
            return self.update(instance, fields_to_update) if fields_to_update else instance
        else:
            return self.create(validated_data)

    def _add_parameters(self, product_info: ProductInfo, product_parameters: list | tuple, replace_old: bool = False):
        if replace_old: product_info.product_parameters.all().delete()

        for parameter_dict in product_parameters:
            try:
                parameter, created = Parameter.objects.get_or_create(name=parameter_dict['parameter'])
                value, created = ValueOfParameter.objects.get_or_create(value=parameter_dict['value'])
                ProductParameter.objects.create(product_info=product_info,
                                                parameter=parameter,
                                                value=value)
            except:
                raise ValidationError({'error': 'bad parameters fields'})

    @property
    def shop(self):
        return self.context['request'].auth.user.shop


class OrderItemBaseSerializer(serializers.ModelSerializer):

    status = serializers.CharField(read_only=True, required=False)

    class Meta:
        model = SellerOrderItem
        fields = ('id', 'product_info', 'quantity', 'order', 'status')


class OrderItemBuyerSerializer(OrderItemBaseSerializer):

    class Meta(OrderItemBaseSerializer.Meta):
        fields = ('product_info', 'quantity', 'order', 'status',)
        extra_kwargs = {
            'order': {'write_only': True},

            'product_info': {'required': True},
            'quantity': {'required': True},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        product_info = data['product_info']
        product_info['price'] = instance.purchase_price
        product_info['price_rrc'] = instance.purchase_price_rrc
        return data


class SellerOrderItemCreateSerializer(OrderItemBuyerSerializer):
    product_info = ProductInfoForOrderSerializer(read_only=True)


class SellerOrderForBasketSerializer(serializers.ModelSerializer):
    shop = ShopSerializer(read_only=True)
    ordered_items = SellerOrderItemCreateSerializer(read_only=True, many=True)

    summary = serializers.IntegerField()

    class Meta:
        model = SellerOrder
        fields = ('id',
                  'shop',
                  'ordered_items',
                  'shipping_price',
                  'summary')


class SellerOrderForBuyerOrderSerializer(SellerOrderForBasketSerializer):
    class Meta(SellerOrderForBasketSerializer.Meta):
        fields = ('id',
                  'shop',
                  'ordered_items',
                  'shipping_price',
                  'updated_at',
                  'state',
                  'summary')


class BasketSerializer(serializers.ModelSerializer):
    seller_orders = SellerOrderForBasketSerializer(read_only=True, many=True)
    total_sum = serializers.IntegerField()

    class Meta:
        model = BuyerOrder
        fields = ('id', 'seller_orders', 'total_sum', )
        read_only_fields = fields


class BuyerOrderSerializer(BasketSerializer):
    seller_orders = SellerOrderForBuyerOrderSerializer(read_only=True, many=True)
    contact = ContactSerializer(read_only=True)

    class Meta(BasketSerializer.Meta):
        fields = ('id', 'seller_orders', 'contact', 'total_sum', 'state', 'created_at', )


class ProductInfoForSellerOrderSerializer(ProductInfoBaseSerializer):
    category = PartnerCategorySerializer()

    class Meta(ProductInfoBaseSerializer.Meta):
        fields = ('id', 'external_id', 'category', 'product', 'product_parameters', 'price', 'price_rrc',)


class PartnerOrderProductsSerializer(OrderItemBuyerSerializer):
    product_info = ProductInfoForSellerOrderSerializer(read_only=True)


class PartnerOrderSerializer(serializers.ModelSerializer):
    ordered_items = PartnerOrderProductsSerializer(read_only=True, many=True)
    state = serializers.ChoiceField(choices=SellerOrderState.choices[1:])

    summary = serializers.IntegerField()
    contact = ContactSerializer()
    created_at = serializers.DateTimeField()

    class Meta:
        model = SellerOrder

        fields = ('id', 'ordered_items', 'contact', 'created_at', 'updated_at', 'state', 'shipping_price', 'summary')
        read_only_fields = ('id', 'ordered_items', 'summary', 'contact', 'created_at', 'updated_at')

    def validate_state(self, value):
        if self.instance.state in {SellerOrderState.canceled, SellerOrderState.delivered}:
            raise serializers.ValidationError('You can not change state of this order')
        return value

    def validate_shipping_price(self, value):
        if self.instance.state not in SellerOrderState.get_cancelable_by_user_states():
            raise serializers.ValidationError('You can not change shipping_price of this order')
        return value

    def update(self, instance, validated_data):
        if new_state := validated_data.get('state'):
            buyer_order = instance.buyer_order
            buyer_email = buyer_order.user.email
            seller_order_id = instance.id

            if new_state == SellerOrderState.canceled:
                instance.rollback_product_quantity(buyer_order)

            subject = f'Order: {buyer_order.id}'
            message = f'Changes in the order: {buyer_order.id}. ' \
                      f'\nStatus of the attached order: {seller_order_id} ' \
                      f'from the store {instance.shop.name} changed to: {new_state}\n\n'

            send_confirmation_email(buyer_email, subject=subject, message=message)

        return super().update(instance, validated_data)


class PartnerStateSerializer(serializers.Serializer):

    state = serializers.ChoiceField(choices=PartnerState.choices)


class PositiveIntegers(serializers.ListSerializer):

    child = serializers.IntegerField(min_value=1)


class CustomPasswordTokenSerializer(PasswordTokenSerializer, PasswordMatchValidateMixin):

    password2 = serializers.CharField()
    validate = PasswordMatchValidateMixin.validate
