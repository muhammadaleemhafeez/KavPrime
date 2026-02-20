from rest_framework import serializers
from .models import Asset
from django.contrib.auth.models import User


class AssetSerializer(serializers.ModelSerializer):

    assigned_to = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(),
        required=False,
        allow_null=True
    )

    class Meta:
        model = Asset
        fields = "__all__"