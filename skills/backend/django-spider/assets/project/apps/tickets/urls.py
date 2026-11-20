from django.urls import path

from apps.tickets.views import (
    TicketAssignView,
    TicketCommentDetailView,
    TicketCommentListCreateView,
    TicketDetailView,
    TicketListCreateView,
    TicketStatusView,
)

urlpatterns = [
    path("", TicketListCreateView.as_view(), name="ticket-list"),
    path("<int:pk>/", TicketDetailView.as_view(), name="ticket-detail"),
    path("<int:pk>/assign/", TicketAssignView.as_view(), name="ticket-assign"),
    path("<int:pk>/status/", TicketStatusView.as_view(), name="ticket-status"),
    path("<int:pk>/comments/", TicketCommentListCreateView.as_view(), name="ticket-comments"),
    path("<int:pk>/comments/<int:comment_id>/", TicketCommentDetailView.as_view(), name="ticket-comment-detail"),
]
