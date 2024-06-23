from django.contrib.auth import authenticate
from django.conf import settings
from django.middleware import csrf
from rest_framework import exceptions as rest_exceptions, response, decorators as rest_decorators, permissions as rest_permissions
from rest_framework_simplejwt import tokens, views as jwt_views, serializers as jwt_serializers, exceptions as jwt_exceptions
from user import serializers, models
import stripe


from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi

stripe.api_key = settings.STRIPE_SECRET_KEY
prices = {
    settings.WORLD_INDIVIDUAL: "world_individual",
    settings.WORLD_GROUP: "world_group",
    settings.WORLD_BUSINESS: "world_business",
    settings.UNIVERSE_INDIVIDUAL: "universe_individual",
    settings.UNIVERSE_GROUP: "universe_group",
    settings.UNIVERSE_BUSINESS: "universe_business"
}
id_param = openapi.Parameter(
    'id',
    openapi.IN_QUERY,
    description='User ID',
    type=openapi.TYPE_INTEGER,
    required=True
)


def get_user_tokens(user):
    refresh = tokens.RefreshToken.for_user(user)
    return {
        "refresh_token": str(refresh),
        "access_token": str(refresh.access_token)
    }


@swagger_auto_schema(
    method='post',
    operation_summary="Login and get access token to authorize other routes. Example email: test@mail.com password: test",
    request_body=serializers.LoginSerializer,
    responses={
        200: openapi.Response(description='Login successfull', schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'refresh_token': openapi.Schema(type=openapi.TYPE_STRING, description='Refresh token'),
                'access_token': openapi.Schema(type=openapi.TYPE_STRING, description='JWT Token'),
            }
        )),
        401: openapi.Response(description='Invalid credentials', schema=openapi.Schema(
            type=openapi.TYPE_OBJECT,
            properties={
                'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Error message'),
            }
        )),
    }
)
@rest_decorators.api_view(["POST"])
@rest_decorators.permission_classes([])
def loginView(request):
    serializer = serializers.LoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    email = serializer.validated_data["email"]
    password = serializer.validated_data["password"]

    user = authenticate(email=email, password=password)

    if user is not None:
        tokens = get_user_tokens(user)
        res = response.Response()
        res.set_cookie(
            key=settings.SIMPLE_JWT['AUTH_COOKIE'],
            value=tokens["access_token"],
            expires=settings.SIMPLE_JWT['ACCESS_TOKEN_LIFETIME'],
            secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
            httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
            samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE']
        )

        res.set_cookie(
            key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
            value=tokens["refresh_token"],
            expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
            secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
            httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
            samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE']
        )

        res.data = tokens
        res["X-CSRFToken"] = csrf.get_token(request)
        return res
    raise rest_exceptions.AuthenticationFailed(
        "Email or Password is incorrect!")


@swagger_auto_schema(
    method='post',
    operation_summary="Register a new user if you don't have an account",
    request_body=serializers.RegistrationSerializer,
    responses={
        200: openapi.Response(
            description='User registered',
            schema=openapi.Schema(
                type=openapi.TYPE_STRING, description='User registered message')),
        400: openapi.Response(description="Invalid credentials", schema=openapi.Schema(type=openapi.TYPE_OBJECT, properties={
            "detail": openapi.Schema(type=openapi.TYPE_STRING, description='Error message')}))}
)
@rest_decorators.api_view(["POST"])
@rest_decorators.permission_classes([])
def registerView(request):
    serializer = serializers.RegistrationSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = serializer.save()

    if user is not None:
        return response.Response("Registered!")
    return rest_exceptions.AuthenticationFailed("Invalid credentials!")


@swagger_auto_schema(
    method='post',
    responses={
        200: openapi.Response(
            description='Logout successful'
        ),
        401: openapi.Response(
            description='Invalid credentials',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Error message'),
                }
            )
        ),
    }

)
@ rest_decorators.api_view(['POST'])
@ rest_decorators.permission_classes([rest_permissions.IsAuthenticated])
def logoutView(request):
    try:
        refreshToken = request.COOKIES.get(
            settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        token = tokens.RefreshToken(refreshToken)
        token.blacklist()

        res = response.Response()
        res.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE'])
        res.delete_cookie(settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'])
        res.delete_cookie("X-CSRFToken")
        res.delete_cookie("csrftoken")
        res["X-CSRFToken"] = None

        print(res)

        return res
    except:
        raise rest_exceptions.ParseError("Invalid token")


class CookieTokenRefreshSerializer(jwt_serializers.TokenRefreshSerializer):
    refresh = None

    def validate(self, attrs):
        attrs['refresh'] = self.context['request'].COOKIES.get('refresh')
        if attrs['refresh']:
            return super().validate(attrs)
        else:
            raise jwt_exceptions.InvalidToken(
                'No valid token found in cookie \'refresh\'')


class CookieTokenRefreshView(jwt_views.TokenRefreshView):
    serializer_class = CookieTokenRefreshSerializer

    def finalize_response(self, request, response, *args, **kwargs):
        if response.data.get("refresh"):
            response.set_cookie(
                key=settings.SIMPLE_JWT['AUTH_COOKIE_REFRESH'],
                value=response.data['refresh'],
                expires=settings.SIMPLE_JWT['REFRESH_TOKEN_LIFETIME'],
                secure=settings.SIMPLE_JWT['AUTH_COOKIE_SECURE'],
                httponly=settings.SIMPLE_JWT['AUTH_COOKIE_HTTP_ONLY'],
                samesite=settings.SIMPLE_JWT['AUTH_COOKIE_SAMESITE']
            )

            del response.data["refresh"]
        response["X-CSRFToken"] = request.COOKIES.get("csrftoken")
        return super().finalize_response(request, response, *args, **kwargs)


@swagger_auto_schema(
    method='post',
    operation_summary="Refresh the access token using the refresh token from cookies.",
    responses={
        200: openapi.Response(
            description='Token refreshed successfully',
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'access': openapi.Schema(type=openapi.TYPE_STRING, description='New access token'),
                }
            )
        ),
        400: openapi.Response(
            description="Invalid or missing refresh token",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Error message')
                }
            )
        )
    }
)
@rest_decorators.api_view(['POST'])
@rest_decorators.permission_classes([rest_permissions.IsAuthenticated])
def token_refresh_view(request):
    view = CookieTokenRefreshView.as_view()
    return view(request)


@swagger_auto_schema(
    method='get',
    operation_summary="Get user details. Example id 2",
    manual_parameters=[id_param],
    responses={
        200: openapi.Response(
            description="User details retrieved successfully",
            schema=serializers.UserSerializer
        ),
        401: openapi.Response(
            description="Authentication credentials were not provided.",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Error message')
                }
            )
        ),
        404: openapi.Response(
            description="User not found",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Error message')
                }
            )
        )
    }
)
@ rest_decorators.api_view(["GET"])
@ rest_decorators.permission_classes([rest_permissions.IsAuthenticated])
def user(request):
    try:
        user = models.User.objects.get(id=request.user.id)
    except models.User.DoesNotExist:
        return response.Response(status_code=404)

    serializer = serializers.UserSerializer(user)
    return response.Response(serializer.data)


@swagger_auto_schema(
    method='get',
    operation_description="Get list of active subscriptions for the authenticated user",
    manual_parameters=[id_param],
    responses={
        200: openapi.Response(
            description="Active subscriptions retrieved successfully",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'subscriptions': openapi.Schema(
                        type=openapi.TYPE_ARRAY,
                        items=openapi.Schema(
                            type=openapi.TYPE_OBJECT,
                            properties={
                                'id': openapi.Schema(type=openapi.TYPE_STRING, description='Subscription ID'),
                                'start_date': openapi.Schema(type=openapi.TYPE_STRING, description='Start date of the subscription'),
                                'plan': openapi.Schema(type=openapi.TYPE_STRING, description='Plan name'),
                            }
                        )
                    )
                }
            )
        ),
        401: openapi.Response(
            description="Authentication credentials were not provided.",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Error message')
                }
            )
        ),
        404: openapi.Response(
            description="Subscriptions not found",
            schema=openapi.Schema(
                type=openapi.TYPE_OBJECT,
                properties={
                    'detail': openapi.Schema(type=openapi.TYPE_STRING, description='Error message')
                }
            )
        )
    }
)
@ rest_decorators.api_view(["GET"])
@ rest_decorators.permission_classes([rest_permissions.IsAuthenticated])
def getSubscriptions(request):
    try:
        user = models.User.objects.get(id=request.user.id)
    except models.User.DoesNotExist:
        return response.Response(status_code=404)

    subscriptions = []
    customer = stripe.Customer.search(query=f'email:"{user.email}"')
    if "data" in customer:
        if len(customer["data"]) > 0:
            for _customer in customer["data"]:
                subscription = stripe.Subscription.list(
                    customer=_customer["id"])
                if "data" in subscription:
                    if len(subscription["data"]) > 0:
                        for _subscription in subscription["data"]:
                            if _subscription["status"] == "active":
                                subscriptions.append({
                                    "id": _subscription["id"],
                                    "start_date": str(_subscription["start_date"]),
                                    "plan": prices[_subscription["plan"]["id"]]
                                })

    return response.Response({"subscriptions": subscriptions}, 200)
