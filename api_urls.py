"""
Main API URLs for MediCureFlow project.
This module consolidates all API endpoints from different apps.
"""

from django.urls import path, include
from rest_framework.response import Response
from rest_framework.decorators import api_view
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView, 
    SpectacularSwaggerView
)
from drf_spectacular.utils import extend_schema
from drf_spectacular.openapi import OpenApiResponse

@extend_schema(
    responses={
        200: OpenApiResponse(
            description="API root with available endpoints",
            response={
                'message': 'string',
                'endpoints': 'object',
                'version': 'string',
                'project': 'string'
            }
        )
    }
)
@api_view(['GET'])
def api_root(request, format=None):
    """API Root endpoint with available endpoints."""
    return Response({
        'message': 'MediCureFlow API v1.0',
        'endpoints': {
            'doctors': request.build_absolute_uri('doctors/'),
            'users': request.build_absolute_uri('users/'),
            'specialties': request.build_absolute_uri('doctors/specialties/'),
            'documentation': {
                'swagger': request.build_absolute_uri('schema/swagger-ui/'),
                'redoc': request.build_absolute_uri('schema/redoc/'),
                'schema': request.build_absolute_uri('schema/')
            }
        },
        'version': '1.0',
        'project': 'MediCureFlow'
    })

app_name = 'api'

urlpatterns = [
    # API Root
    path('', api_root, name='root'),
    
    # API Documentation
    path('schema/', SpectacularAPIView.as_view(), name='schema'),
    path('schema/swagger-ui/', SpectacularSwaggerView.as_view(url_name='api:schema'), name='swagger-ui'),
    path('schema/redoc/', SpectacularRedocView.as_view(url_name='api:schema'), name='redoc'),
    
    # API Version 1
    path('v1/doctors/', include('apps.doctors.api_urls', namespace='v1_doctors')),
    path('v1/users/', include('apps.users.api_urls', namespace='v1_users')),
    
    # Main API endpoints
    path('doctors/', include('apps.doctors.api_urls')),
    path('users/', include('apps.users.api_urls')),
]
