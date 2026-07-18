from rest_framework import viewsets, permissions, serializers
from rest_framework.response import Response

class ConsultantSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.cv_extractor.models import Consultant
        model = Consultant
        fields = ['id', 'aid', 'first_name', 'last_name', 'email', 'status']

class ConsultantViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConsultantSerializer
    def get_queryset(self):
        from apps.cv_extractor.models import Consultant
        return Consultant.objects.all()

class CVViewSet(viewsets.ViewSet):
    pass

class EmailViewSet(viewsets.ViewSet):
    pass
