from django.contrib.auth import authenticate
from django.db import IntegrityError
from django.db.models import Prefetch
from django_rest_passwordreset.views import ResetPasswordConfirm
from rest_framework import mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from .filters import ProductFilter, PartnerProductFilter, SellerOrderFilter
from .permissions import IsPartner, IsShopOwnerOrReadOnly
from .serializers import UserSerializer, ShopSerializer, ProductInfoSerializer, PartnerProductInfoSerializer, \
    CategorySerializer, ContactSerializer, OrderItemBuyerSerializer, BuyerOrderSerializer, \
    PartnerOrderSerializer, PartnerStateSerializer, AuthenticateSerializer, PositiveIntegers, \
    CustomPasswordTokenSerializer, SellerOrderForBuyerOrderSerializer
from .models import User, ConfirmRegistrationToken, Shop, Category, ProductInfo, \
    BuyerOrder, SellerOrder, SellerOrderItem
from rest_framework.viewsets import GenericViewSet, ModelViewSet, ReadOnlyModelViewSet
from .email_sender import send_confirmation_email
import yaml
from .app_choices import SellerOrderState, BuyerOrderState, PartnerState, UserConfirmation
from .filters import BuyerOrderFilter
from django.utils import timezone
from .serializers import BasketSerializer


class UserFromRequestMixin:
    @property
    def user(self):
        return self.request.auth.user


class PartnerPaginationMixin:
    def get_paginated_response(self, data):
        response = super().get_paginated_response(data)
        shop = ShopSerializer(self.request.user.shop).data
        response.data = {'shop': shop, **response.data}
        return response


class CustomResetPasswordConfirm(ResetPasswordConfirm):
    serializer_class = CustomPasswordTokenSerializer


class UserViewSet(mixins.CreateModelMixin,
                  mixins.RetrieveModelMixin,
                  mixins.UpdateModelMixin,
                  GenericViewSet,
                  UserFromRequestMixin):
    queryset = User.objects.all()
    serializer_class = UserSerializer

    def get_object(self):
        return self.user

    def get_permissions(self):
        """Получение прав для действий."""
        if self.action != 'create':
            return [IsAuthenticated()]
        return []


class AuthenticateView(APIView):

    def post(self, request, *args, **kwargs):

        credentials = request.data

        credentials_serializer = AuthenticateSerializer(data=credentials)
        credentials_serializer.is_valid(raise_exception=True)

        user = authenticate(request, username=credentials['email'], password=credentials['password'])

        if not user:
            return Response({'error': 'incorrect credentials'}, status.HTTP_418_IM_A_TEAPOT)
        elif user.need_confirmation:
            return Response({'error': 'your email has not been confirmed'}, status.HTTP_400_BAD_REQUEST)

        return Response(user.auth_token.key, status.HTTP_200_OK)


class ConfirmEmailView(APIView):

    def get(self, request, temp_token, *args, **kwargs):
        confirm_token_obj = ConfirmRegistrationToken.objects.filter(token=temp_token).select_related('user').first()
        if not confirm_token_obj:
            return Response({'error': 'incorrect link'}, status=status.HTTP_400_BAD_REQUEST)
        user = confirm_token_obj.user
        token_key = user.create_auth_token()
        if user.need_confirmation == UserConfirmation.need_admin:
            user.is_superuser = True
            user.is_staff = True
        user.need_confirmation = UserConfirmation.confirmed
        user.save()
        confirm_token_obj.delete()
        return Response({'token': token_key}, status=status.HTTP_200_OK)


class ShopView(mixins.CreateModelMixin,
               mixins.RetrieveModelMixin,
               mixins.UpdateModelMixin,
               mixins.ListModelMixin,
               GenericViewSet):
    queryset = Shop.objects.all()
    serializer_class = ShopSerializer

    def get_permissions(self):
        """Получение прав для действий."""
        permissions = [IsShopOwnerOrReadOnly()]
        if self.action in {'create', 'update', 'partial_update'}:
            permissions.append(IsAuthenticated())
        return permissions


class CategoryView(ReadOnlyModelViewSet):
    queryset = Category.objects.all()
    serializer_class = CategorySerializer


class ProductView(ReadOnlyModelViewSet):
    serializer_class = ProductInfoSerializer

    filterset_class = ProductFilter

    def get_queryset(self, *args, **kwargs):
        return ProductInfo.objects.filter(shop__is_open=True, quantity__gt=0).all()


class PartnerProductView(PartnerPaginationMixin, ModelViewSet, UserFromRequestMixin):
    serializer_class = PartnerProductInfoSerializer
    filterset_class = PartnerProductFilter

    def get_permissions(self):
        """Получение прав для действий."""
        permissions = [IsAuthenticated()]
        if self.action != 'create_catalogue':
            permissions.append(IsPartner())
        return permissions

    @action(detail=False, methods=['post'], url_path='upload', url_name='upload')
    def create_catalogue(self, request, *args, **kwargs):
        user = self.user

        try:
            uploaded_file = request.FILES['file']
            yaml_data = uploaded_file.read().decode('utf-8')
            json_data = yaml.safe_load(yaml_data)
            shop_name = json_data['shop']
            categories_source = json_data['categories']
            categories = {category['id']: {'name': category['name'], 'external_id': category['id']}
                          for category in categories_source}
            products = json_data['goods']
        except:
            return Response({'error': 'unable to load data from the file'}, status=status.HTTP_400_BAD_REQUEST)

        shop_email = json_data.get('email', user.email)
        shop_base_shipping_price = int(json_data.get('shipping_price', 300))
        try:
            shop, shop_created = \
                Shop.objects.get_or_create(owner=user, defaults={'name': shop_name,
                                                                 'email': shop_email,
                                                                 'base_shipping_price': shop_base_shipping_price})
        except IntegrityError:
            return Response({'error': f'{shop_name}: this shop_name is already occupied'},
                            status=status.HTTP_403_FORBIDDEN)

        validated_product_infos = []

        for product_source in products:
            __source_info = {'categories': categories_source, 'product': product_source}

            try:
                category_external_id = product_source['category']
                category = categories[category_external_id]
            except KeyError as error:
                return Response({'category_error': 'parse or matching error', 'key': str(error)} | __source_info,
                                status=status.HTTP_400_BAD_REQUEST)

            try:
                product_parameters = [dict(zip(('parameter', 'value'), i))
                                      for i in product_source['parameters'].items()]

                product_data = {'external_id': product_source['id'],
                                'category': category,
                                'product': {'name': product_source['name']},
                                'product_parameters': product_parameters,
                                'price': product_source['price'],
                                'price_rrc': product_source['price_rrc'],
                                'quantity': product_source['quantity']}

            except KeyError as error:
                return Response({'product_error': 'parse', 'invalid_field': str(error)} | __source_info,
                                status=status.HTTP_400_BAD_REQUEST)

            product_info_serializer = self.get_serializer(data=product_data)

            try:
                product_info_serializer.is_valid(raise_exception=True)
            except ValidationError as error:
                return Response({'product': product_source} | error.detail, status=status.HTTP_400_BAD_REQUEST)

            validated_product_infos.append(product_info_serializer.validated_data)

        if shop_created or not shop.product_infos.exists():
            for product_info in validated_product_infos:
                self.get_serializer().create(product_info)
        else:
            shop.product_infos.exclude(external_id__in={product_info['external_id']
                                                        for product_info in validated_product_infos}).update(quantity=0)

            for product_info in validated_product_infos:
                self.get_serializer().update_or_create(product_info)

        return Response({'status': 'ok'}, status=status.HTTP_201_CREATED)

    def perform_destroy(self, instance):
        instance.quantity = 0
        instance.save()

    def get_queryset(self, *args, **kwargs):
        return self.user.shop.product_infos.all()


class PartnerStateView(APIView, UserFromRequestMixin):
    permission_classes = [IsAuthenticated, IsPartner]

    @property
    def users_shop(self):
        return self.user.shop

    def get(self, request):
        return Response({'Your shop is open': self.users_shop.is_open}, status=status.HTTP_200_OK)

    def post(self, request):
        states = {PartnerState.open: True, PartnerState.closed: False}

        state_serializer = PartnerStateSerializer(data=request.data)
        state_serializer.is_valid(raise_exception=True)

        new_state = state_serializer.validated_data['state']
        new_state = states[new_state]

        self.users_shop.is_open = new_state
        self.users_shop.save()
        return Response({'Your shop is open': new_state}, status=status.HTTP_201_CREATED)


class ContactView(ModelViewSet, UserFromRequestMixin):
    serializer_class = ContactSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self, *args, **kwargs):
        return self.user.contacts.filter(is_deleted=False).all()

    def perform_destroy(self, instance):
        instance.is_deleted = True
        instance.save()


class BasketView(APIView, UserFromRequestMixin):
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        basket = []
        if _basket_object := self.user.basket_object: basket.append(_basket_object)
        return Response(BasketSerializer(basket, many=True).data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        basket = self.user.basket_object or BuyerOrder.objects.create(user=self.request.auth.user,
                                                                      state=BuyerOrderState.basket)

        ordered_items_serializer = OrderItemBuyerSerializer(data=request.data, many=True)
        ordered_items_serializer.is_valid(raise_exception=True)

        validated_ordered_items = {ordered_item_dict['product_info'].id: ordered_item_dict['quantity']
                                   for ordered_item_dict in ordered_items_serializer.validated_data}

        shops_with_ordered_products = \
            Shop.objects.filter(is_open=True,
                                product_infos__id__in=validated_ordered_items.keys()) \
                .prefetch_related(Prefetch('product_infos',
                                           queryset=ProductInfo.objects.filter(id__in=validated_ordered_items.keys())),
                                  'product_infos__product')

        for shop in shops_with_ordered_products:
            order, created = SellerOrder.objects.get_or_create(buyer_order=basket,
                                                               shop=shop,
                                                               state=SellerOrderState.basket,
                                                               defaults={'shipping_price': shop.base_shipping_price})
            for product_info in shop.product_infos.all():
                SellerOrderItem.objects.update_or_create(order=order,
                                                         product_info=product_info,
                                                         defaults={'quantity': validated_ordered_items[product_info.id],
                                                                   'purchase_price': product_info.price,
                                                                   'purchase_price_rrc': product_info.price_rrc})

        return Response(BasketSerializer(basket).data, status=status.HTTP_201_CREATED)

    def delete(self, request, *args, **kwargs):
        ids_to_del = request.data

        PositiveIntegers(data=ids_to_del).is_valid(raise_exception=True)

        basket = self.user.basket_queryset.prefetch_related('seller_orders__shop',
                                                            'seller_orders__ordered_items',
                                                            'seller_orders__ordered_items__product_info').first()

        if not basket:
            return Response({'error': f'Your basket does not exists'}, status=status.HTTP_400_BAD_REQUEST)

        ids_to_del = set(ids_to_del)
        seller_orders_baskets = basket.seller_orders.all()

        all_ordered_ids = {ordered_item.product_info.id for seller_order in seller_orders_baskets
                           for ordered_item in seller_order.ordered_items.all()}
        unknown_ids = ids_to_del - all_ordered_ids

        if unknown_ids:
            unknown_ids = ', '.join(map(str, unknown_ids))
            return Response({'error': f'Unknown ids {unknown_ids}'}, status=status.HTTP_400_BAD_REQUEST)

        if basket.state == BuyerOrderState.basket and ids_to_del == all_ordered_ids:
            basket.delete()
            return Response([], status=status.HTTP_204_NO_CONTENT)

        seller_orders_to_del = {}
        ordered_items_to_del = set()

        for seller_order in seller_orders_baskets:
            ordered_items = seller_order.ordered_items.all()
            ordered_items = {ordered_item: ordered_item.product_info.id for ordered_item in ordered_items}
            ordered_product_ids = set(ordered_items.values())
            items_to_del_in_current_order = ordered_product_ids & ids_to_del
            if not items_to_del_in_current_order:
                continue

            if ordered_product_ids == items_to_del_in_current_order:
                seller_orders_to_del[seller_order.id] = seller_order
            else:
                ordered_objects_to_del = (k for k, v in ordered_items.items() if v in items_to_del_in_current_order)

                for ordered_object in ordered_objects_to_del:
                    ordered_items_to_del.add(ordered_object.id)
                    seller_order.ordered_items.remove(ordered_object)

            ids_to_del -= items_to_del_in_current_order

            if not ids_to_del:
                break

        if seller_orders_to_del:
            basket.seller_orders.filter(id__in=seller_orders_to_del).delete()
            for seller_object in seller_orders_to_del.values():
                basket.seller_orders.remove(seller_object)

        if ordered_items_to_del:
            SellerOrderItem.objects.filter(id__in=ordered_items_to_del).delete()

        return Response(BasketSerializer(basket).data, status=status.HTTP_204_NO_CONTENT)


class OrderViewSet(mixins.CreateModelMixin,
                   mixins.ListModelMixin,
                   mixins.RetrieveModelMixin,
                   GenericViewSet,
                   UserFromRequestMixin):
    permission_classes = [IsAuthenticated]
    serializer_class = BuyerOrderSerializer
    filterset_class = BuyerOrderFilter

    def get_queryset(self, *args, **kwargs):
        return self.user.orders.exclude(state=BuyerOrderState.basket).all()

    def create(self, request, *args, **kwargs):
        user = self.user

        order = user.basket_queryset.prefetch_related('seller_orders__shop',
                                                      'seller_orders__ordered_items',
                                                      'seller_orders__ordered_items__product_info',
                                                      'seller_orders__ordered_items__product_info__product').first()
        if not order:
            return Response({'error': 'no order to confirm'}, status=status.HTTP_204_NO_CONTENT)

        contact_id = request.data.get('contact')

        if not isinstance(contact_id, int) or contact_id <= 0:
            return Response({'error': 'bad contact'}, status=status.HTTP_400_BAD_REQUEST)

        users_contact = user.contacts.filter(id=contact_id).first()

        if not users_contact:
            return Response({'error': 'contact not found'}, status=status.HTTP_400_BAD_REQUEST)

        all_orders = order.seller_orders.all()

        acceptable_order = True
        quantity_to_update = {}
        ordered_items_strs = {}

        # проверка, какие товары заказаны больше, чем в наличии
        for seller_order in all_orders:

            ordered_items = seller_order.ordered_items.all()

            for ordered_item in ordered_items:
                ordered_product_info = PartnerProductInfoSerializer(ordered_item.product_info).data
                ordered_quantity = ordered_item.quantity
                available_quantity = ordered_product_info['quantity']
                result_quantity = available_quantity - ordered_quantity

                if result_quantity < 0:
                    acceptable_order = False
                    message = f'too many ordered. You ordered {ordered_quantity} pcs, ' \
                              f'but only {available_quantity} pcs in stock'
                    ordered_item.status = message

                elif acceptable_order:
                    quantity_to_update[ordered_product_info['id']] = result_quantity
                    current_order_ordered_items_strs = ordered_items_strs.setdefault(seller_order.id, [])
                    current_order_ordered_items_strs.append(f'id: {ordered_product_info["id"]}, '
                                                            f'external_id: {ordered_product_info["external_id"]}, '
                                                            f'quantity: {ordered_item.quantity}')

        if acceptable_order:
            # подтверждение заказа продавца
            current_date = timezone.now()
            for seller_order in all_orders:

                for ordered_item in seller_order.ordered_items.all():
                    ordered_product_info_id = ordered_item.product_info.id
                    ProductInfo.objects.filter(id=ordered_product_info_id) \
                        .update(quantity=quantity_to_update[ordered_product_info_id])

                seller_order.contact = users_contact
                seller_order.state = SellerOrderState.new
                seller_order.created_at = current_date
                seller_order.save()

                subject = f'Новый заказ {seller_order.id}'
                message = f'{subject}\nТовары:\n{"".join(ordered_items_strs[seller_order.id])}\n' \
                          f'Доставить по адресу:\n{str(users_contact)}\n' \
                          f'Итог: {seller_order.summary}'

                send_confirmation_email(seller_order.shop.email, subject=subject, message=message)

            order.state = BuyerOrderState.accepted
            order.created_at = current_date
            order.save()

            # уведомление покупателя
            ordered_items = []
            summary_shipping_price = 0

            for seller_order in order.seller_orders.all():
                for ordered_item in seller_order.ordered_items.all():
                    product_info = ordered_item.product_info
                    info = f'Товар: {product_info.product.name}, ' \
                           f'количество: {ordered_item.quantity}, ' \
                           f'сумма: {ordered_item.quantity * product_info.price}'
                    ordered_items.append(info)
                summary_shipping_price += seller_order.shipping_price

            ordered_items = '\n'.join(ordered_items)

            subject = f'Заказ {order.id}'
            message = f'Спасибо за {subject.lower()}!\n\n' \
                      f'Заказанные товары: \n{ordered_items}\n' \
                      f'Доставка по адресу: \n\n{str(users_contact)}\n' \
                      f'Суммарная цена доставки: {summary_shipping_price}\n' \
                      f'Итог: {order.total_sum}'

            send_confirmation_email(user.email, subject=subject, message=message)

        return Response(self.get_serializer(order).data,
                        status=status.HTTP_201_CREATED if acceptable_order else status.HTTP_206_PARTIAL_CONTENT)


class BuyerSellerOrderView(mixins.DestroyModelMixin,
                           GenericViewSet,
                           UserFromRequestMixin):
    permission_classes = [IsAuthenticated]
    serializer_class = SellerOrderForBuyerOrderSerializer

    def get_queryset(self):
        return SellerOrder.objects.filter(buyer_order__user_id=self.user.id,
                                          state__in=SellerOrderState.get_cancelable_by_user_states()
                                          ).prefetch_related('ordered_items',
                                                             'ordered_items__product_info').all()

    def perform_destroy(self, seller_order_instance):
        buyer_order = seller_order_instance.buyer_order

        if seller_order_instance.state == SellerOrderState.basket:
            seller_order_instance.delete()

            if not buyer_order.seller_orders.exists():
                buyer_order.delete()
                return
        else:
            seller_order_instance.rollback_product_quantity(buyer_order)

            seller_order_instance.state = SellerOrderState.canceled
            seller_order_instance.save()

            seller_email = seller_order_instance.shop.email
            subject = f'Заказ {seller_order_instance.id} отменён'
            message = f'{subject} пользователем. Товары возвращены на склад.'
            send_confirmation_email(seller_email, subject=subject, message=message)


class PartnerOrderView(PartnerPaginationMixin,
                       mixins.RetrieveModelMixin,
                       # продавец может менять только state и shipping_price
                       mixins.UpdateModelMixin,
                       mixins.ListModelMixin,
                       GenericViewSet,
                       UserFromRequestMixin):
    permission_classes = [IsAuthenticated, IsPartner]
    serializer_class = PartnerOrderSerializer
    filterset_class = SellerOrderFilter

    def get_queryset(self):
        return self.user.shop.orders.exclude(state=SellerOrderState.basket).all()
