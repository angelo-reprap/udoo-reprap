"""
API Views for Email Log Search
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page

from .search import EmailLogSearch
try:
    from .signals import bulk_index_email_logs, init_index
except ImportError as e:
    print(f"⚠️  Signals import failed: {e}")
    # Define fallback functions
    def bulk_index_email_logs(*args, **kwargs):
        return 0
    
    def init_index(*args, **kwargs):
        return False, 0

class EmailSearchAPI(APIView):
    """
    API for searching EmailLogs
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Search emails with various filters
        """
        query_params = request.GET
        
        # Initialize search
        search = EmailLogDocument.search()
        
        # Apply filters
        if 'q' in query_params:
            query = query_params['q']
            search = EmailLogSearch.fulltext_search(query)
        
        if 'person_id' in query_params:
            person_id = query_params['person_id']
            search = EmailLogSearch.search_by_person(person_id)
        
        if 'email' in query_params:
            email = query_params['email']
            search = EmailLogSearch.search_by_email(email)
        
        if 'start_date' in query_params:
            start_date = query_params['start_date']
            end_date = query_params.get('end_date')
            search = EmailLogSearch.search_by_date_range(start_date, end_date)
        
        # Pagination
        page = int(query_params.get('page', 1))
        size = int(query_params.get('size', 20))
        offset = (page - 1) * size
        
        search = search.params(from_=offset, size=size)
        
        # Execute search
        try:
            response = search.execute()
            
            # Format results
            results = []
            for hit in response:
                result = hit.to_dict()
                result['_score'] = hit.meta.score
                result['_id'] = hit.meta.id
                results.append(result)
            
            return Response({
                'total': response.hits.total.value,
                'page': page,
                'size': size,
                'results': results
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class EmailStatsAPI(APIView):
    """
    API for email statistics
    """
    permission_classes = [IsAuthenticated]
    
    @method_decorator(cache_page(60 * 5))  # Cache for 5 minutes
    def get(self, request):
        """
        Get email statistics
        """
        try:
            stats = EmailLogSearch.get_stats()
            return Response(stats)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class EmailTimelineAPI(APIView):
    """
    API for email timeline
    """
    permission_classes = [IsAuthenticated]
    
    def get(self, request, person_id=None):
        """
        Get email timeline for a person or all emails
        """
        try:
            if person_id:
                search = EmailLogSearch.search_by_person(person_id, size=200)
            else:
                search = EmailLogDocument.search()
                search = search.sort('-sent_received_at')
                search = search.params(size=200)
            
            response = search.execute()
            
            # Group by date
            timeline = {}
            for hit in response:
                if hit.sent_received_at:
                    date_str = hit.sent_received_at.strftime('%Y-%m-%d')
                    if date_str not in timeline:
                        timeline[date_str] = []
                    
                    timeline[date_str].append({
                        'id': hit.meta.id,
                        'time': hit.sent_received_at.strftime('%H:%M'),
                        'subject': hit.subject,
                        'from': hit.from_email,
                        'direction': hit.direction,
                        'has_attachments': hit.attachments_count > 0
                    })
            
            # Convert to list sorted by date
            timeline_list = [
                {
                    'date': date,
                    'emails': emails
                }
                for date, emails in sorted(timeline.items(), reverse=True)
            ]
            
            return Response({
                'total': response.hits.total.value,
                'timeline': timeline_list
            })
            
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class EmailReindexAPI(APIView):
    """
    API for reindexing emails (admin only)
    """
    permission_classes = [IsAuthenticated]
    
    def post(self, request):
        """
        Reindex all emails
        """
        # Check if user is staff/admin
        if not request.user.is_staff:
            return Response(
                {'error': 'Permission denied'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        try:
            # Initialize index
            success = init_index()
            
            if success:
                return Response({
                    'message': 'Email index reinitialized successfully',
                    'status': 'success'
                })
            else:
                return Response({
                    'message': 'Failed to reinitialize index',
                    'status': 'error'
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
                
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class EmailHealthAPI(APIView):
    """
    API for email search health check
    """
    def get(self, request):
        """
        Check email search health
        """
        try:
            from elasticsearch_dsl.connections import get_connection
            
            es = get_connection()
            info = es.info()
            
            # Check index exists
            index_exists = EmailLogDocument._index.exists()
            
            # Get document count
            if index_exists:
                count = EmailLogDocument.search().count()
            else:
                count = 0
            
            return Response({
                'elasticsearch': {
                    'status': 'available',
                    'version': info['version']['number'],
                    'cluster': info['cluster_name']
                },
                'email_index': {
                    'exists': index_exists,
                    'document_count': count
                },
                'status': 'healthy' if index_exists else 'index_missing'
            })
            
        except Exception as e:
            return Response({
                'elasticsearch': {
                    'status': 'unavailable',
                    'error': str(e)
                },
                'email_index': {
                    'exists': False,
                    'document_count': 0
                },
                'status': 'unhealthy'
            }, status=status.HTTP_503_SERVICE_UNAVAILABLE)
