"""
ABpE UI Serializers
Für REST API mit Django REST Framework
"""

from rest_framework import serializers
from django.contrib.auth.models import User


class UserSerializer(serializers.ModelSerializer):
    """Serializer für Django User Model"""
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'is_staff']


# Platzhalter für zukünftige Model-Serializer
# (wenn Models erstellt werden, hier einfügen)

class ConsultantProfileSerializer(serializers.Serializer):
    """Platzhalter für Berater-Profil Serializer"""
    id = serializers.IntegerField()
    user_id = serializers.IntegerField()
    berater_id = serializers.CharField()
    position = serializers.CharField(required=False)
    telefon = serializers.CharField(required=False)
    status = serializers.CharField()
    cv_public = serializers.BooleanField()


class CVVersionSerializer(serializers.Serializer):
    """Platzhalter für CV Version Serializer"""
    id = serializers.IntegerField()
    berater_id = serializers.IntegerField()
    version = serializers.IntegerField()
    cv_data = serializers.JSONField()
    created_at = serializers.DateTimeField()
    change_note = serializers.CharField(required=False)
