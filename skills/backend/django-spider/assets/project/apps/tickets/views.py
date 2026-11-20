from rest_framework import generics, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdministrator, IsCustomer
from apps.tickets.helpers import TicketHelper
from apps.tickets.serializers import (
    CommentSerializer,
    CommentWriteSerializer,
    TicketAssignSerializer,
    TicketCreateSerializer,
    TicketListParamsSerializer,
    TicketSerializer,
    TicketStatusSerializer,
)


class TicketListCreateView(generics.ListAPIView):
    """GET: the user's tickets (filtered, paginated). POST: a customer opens a ticket."""

    serializer_class = TicketSerializer

    def get_permissions(self):
        return [IsAuthenticated(), IsCustomer()] if self.request.method == "POST" else [IsAuthenticated()]

    def get_queryset(self):
        params = TicketListParamsSerializer(data=self.request.query_params)
        params.is_valid(raise_exception=True)
        return TicketHelper.list_tickets(self.request.user, params.validated_data)

    def post(self, request):
        serializer = TicketCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = TicketHelper.create_ticket(request.user, serializer.validated_data)
        return Response(TicketSerializer(ticket).data, status=status.HTTP_201_CREATED)


class TicketDetailView(generics.RetrieveAPIView):
    """GET: one ticket the user may see (others are 404)."""

    serializer_class = TicketSerializer

    def get_queryset(self):
        return TicketHelper.get_tickets_for_user(self.request.user)


class TicketAssignView(APIView):
    """PATCH: administrators assign a ticket to an agent."""

    permission_classes = [IsAuthenticated, IsAdministrator]

    def patch(self, request, pk: int):
        serializer = TicketAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = TicketHelper.assign_ticket(pk, serializer.validated_data["agent"], request.user)
        return Response(TicketSerializer(ticket).data)


class TicketStatusView(APIView):
    """PATCH: change a ticket's status along the allowed transitions."""

    def patch(self, request, pk: int):
        serializer = TicketStatusSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        ticket = TicketHelper.change_status(pk, serializer.validated_data["status"], request.user)
        return Response(TicketSerializer(ticket).data)


class TicketCommentListCreateView(generics.ListAPIView):
    """GET: comments of a visible ticket. POST: add one."""

    serializer_class = CommentSerializer

    def get_queryset(self):
        return TicketHelper.list_comments(self.request.user, self.kwargs["pk"])

    def post(self, request, pk: int):
        serializer = CommentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = TicketHelper.add_comment(request.user, pk, serializer.validated_data["body"])
        return Response(CommentSerializer(comment).data, status=status.HTTP_201_CREATED)


class TicketCommentDetailView(APIView):
    """PATCH / DELETE: the author edits or removes their comment (one view, both methods)."""

    def patch(self, request, pk: int, comment_id: int):
        serializer = CommentWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        comment = TicketHelper.update_comment(request.user, pk, comment_id, serializer.validated_data["body"])
        return Response(CommentSerializer(comment).data)

    def delete(self, request, pk: int, comment_id: int):
        TicketHelper.delete_comment(request.user, pk, comment_id)
        return Response(status=status.HTTP_204_NO_CONTENT)
