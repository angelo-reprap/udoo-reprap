from rest_framework import viewsets, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from drf_spectacular.utils import extend_schema, extend_schema_view, OpenApiResponse, OpenApiParameter, inline_serializer
from drf_spectacular.types import OpenApiTypes


# ============================================================
# SERIALIZER
# ============================================================

class ConsultantSerializer(serializers.ModelSerializer):
    class Meta:
        from apps.cv_extractor.models import Consultant
        model = Consultant
        fields = ['id', 'aid', 'first_name', 'last_name', 'email', 'status', 'location']


class CVListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    aid = serializers.CharField()
    name = serializers.CharField()


class EmailListSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    subject = serializers.CharField()
    from_email = serializers.CharField()
    received_date = serializers.DateTimeField()


class UnreadCountSerializer(serializers.Serializer):
    unread_count = serializers.IntegerField()


# ============================================================
# CONSULTANT VIEWSET
# ============================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste aller Berater",
        description="Gibt eine Liste aller Berater zurück",
        responses={200: ConsultantSerializer(many=True)}
    ),
    retrieve=extend_schema(
        summary="Beraterdetails",
        description="Gibt die Details eines bestimmten Beraters zurück",
        responses={200: ConsultantSerializer}
    ),
    create=extend_schema(
        summary="Berater anlegen",
        description="Legt einen neuen Berater an",
        responses={201: ConsultantSerializer}
    ),
    update=extend_schema(
        summary="Berater aktualisieren",
        description="Aktualisiert einen bestehenden Berater",
        responses={200: ConsultantSerializer}
    ),
    partial_update=extend_schema(
        summary="Berater teilweise aktualisieren",
        description="Aktualisiert teilweise einen bestehenden Berater",
        responses={200: ConsultantSerializer}
    ),
    destroy=extend_schema(
        summary="Berater löschen",
        description="Löscht einen Berater",
        responses={204: OpenApiResponse(description="Erfolgreich gelöscht")}
    ),
)
class ConsultantViewSet(viewsets.ModelViewSet):
    permission_classes = [permissions.IsAuthenticated]
    serializer_class = ConsultantSerializer

    def get_queryset(self):
        from apps.cv_extractor.models import Consultant
        return Consultant.objects.all()


# ============================================================
# CV VIEWSET
# ============================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste aller CVs",
        description="Gibt eine Liste aller Berater mit CV zurück",
        responses={200: CVListSerializer(many=True)}
    ),
    my_cv=extend_schema(
        summary="Eigenes CV",
        description="Gibt das CV des aktuell eingeloggten Benutzers zurück",
        responses={200: OpenApiResponse(description="CV-Informationen")}
    ),
)
class CVViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        from apps.cv_extractor.models import Consultant
        consultants = Consultant.objects.filter(cv_data__isnull=False).exclude(cv_data={})
        data = [{'id': c.id, 'aid': c.aid, 'name': f"{c.first_name} {c.last_name}".strip()} for c in consultants]
        return Response(data)

    @action(detail=False, methods=['get'], url_path='my-cv', url_name='my_cv')
    def my_cv(self, request):
        return Response({'message': 'CV Funktionen über cv_extractor'})


# ============================================================
# EMAIL VIEWSET
# ============================================================

@extend_schema_view(
    list=extend_schema(
        summary="Liste aller E-Mails",
        description="Gibt eine Liste der letzten 50 E-Mails zurück",
        responses={200: EmailListSerializer(many=True)}
    ),
    unread_count=extend_schema(
        summary="Anzahl ungelesener E-Mails",
        description="Gibt die Anzahl der ungelesenen E-Mails zurück",
        responses={200: UnreadCountSerializer}
    ),
)
class EmailViewSet(viewsets.ViewSet):
    permission_classes = [permissions.IsAuthenticated]

    def list(self, request):
        from apps.ingest_email.models import EmailMessage
        emails = EmailMessage.objects.all()[:50]
        data = [{'id': e.id, 'subject': e.subject, 'from_email': e.from_email, 'received_date': e.received_date} for e in emails]
        return Response(data)

    @action(detail=False, methods=['get'], url_path='unread-count', url_name='unread_count')
    def unread_count(self, request):
        from apps.ingest_email.models import EmailMessage
        count = EmailMessage.objects.filter(status='NEW').count()
        return Response({'unread_count': count})
