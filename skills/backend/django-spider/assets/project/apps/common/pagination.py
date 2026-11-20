from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class StandardPagination(PageNumberPagination):
    """?page=&page_size= pagination returning the same list shape as the other frameworks."""

    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 100

    def get_paginated_response(self, data: list) -> Response:
        """{"items", "page", "page_size", "total", "total_pages"}."""
        return Response({
            "items": data,
            "page": self.page.number,
            "page_size": self.get_page_size(self.request),
            "total": self.page.paginator.count,
            "total_pages": self.page.paginator.num_pages,
        })
