from rest_framework import viewsets, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view

# ============================================================
# SERIALIZER
# ============================================================
class ConsultantSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()
    email = serializers.EmailField()
    status = serializers.CharField()

class CVSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    consultant_id = serializers.IntegerField()
    version = serializers.IntegerField()

class EmailSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    subject = serializers.CharField()
    from_email = serializers.EmailField()
    is_read = serializers.BooleanField()


# ============================================================
# CONSULTANT VIEWSET
# ============================================================
@extend_schema_view(
    list=extend_schema(summary="Liste aller Berater"),
    retrieve=extend_schema(summary="Berater Detail"),
)
class ConsultantViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        from apps.cv_extractor.models import Consultant
        consultants = Consultant.objects.all()[:50]
        data = [{'id': c.id, 'name': f"{c.first_name} {c.last_name}", 'email': c.email, 'status': c.status} for c in consultants]
        return Response(data)
    
    def retrieve(self, request, pk=None):
        from apps.cv_extractor.models import Consultant
        try:
            c = Consultant.objects.get(id=pk)
            data = {'id': c.id, 'name': f"{c.first_name} {c.last_name}", 'email': c.email, 'status': c.status}
            return Response(data)
        except:
            return Response({'error': 'Not found'}, status=404)
    
    @action(detail=False, methods=['get'])
    def me(self, request):
        return Response({'id': request.user.id, 'username': request.user.username, 'email': request.user.email})


# ============================================================
# CV VIEWSET
# ============================================================
class CVViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        return Response([])
    
    @action(detail=False, methods=['get'])
    def my_cv(self, request):
        from apps.abpe_ui.models import UserSettings
        return Response({'version': 1, 'data': {}})
    
    @action(detail=False, methods=['post'])
    def sync(self, request):
        return Response({'status': 'ok'})


# ============================================================
# EMAIL VIEWSET
# ============================================================
class EmailViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]
    
    def list(self, request):
        from apps.ingest_email.models import EmailMessage
        emails = EmailMessage.objects.all()[:20]
        data = [{'id': e.id, 'subject': e.subject, 'from_email': e.from_email, 'is_read': e.status == 'NEW'} for e in emails]
        return Response(data)
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        from apps.ingest_email.models import EmailMessage
        count = EmailMessage.objects.filter(status='NEW').count()
        return Response({'unread_count': count})
