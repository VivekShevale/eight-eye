from rest_framework import serializers

from apps.accounts.models import User
from apps.tickets.models import Ticket, TicketComment


class TicketCreateSerializer(serializers.ModelSerializer):
    """Fields a customer may send; owner and status are set by the server."""

    class Meta:
        model = Ticket
        fields = ("title", "description", "priority")


class TicketSerializer(serializers.ModelSerializer):
    """A ticket as returned to the people allowed to see it."""

    customer_email = serializers.EmailField(source="customer.email", read_only=True)
    assigned_agent_email = serializers.EmailField(source="assigned_agent.email", read_only=True, allow_null=True)

    class Meta:
        model = Ticket
        fields = ("id", "title", "description", "status", "priority", "customer_email", "assigned_agent_email", "created_at", "updated_at")
        read_only_fields = fields


class TicketListParamsSerializer(serializers.Serializer):
    """Validated query parameters for the ticket list (page/page_size are handled by the paginator)."""

    status = serializers.ChoiceField(choices=Ticket.Status.choices, required=False)
    priority = serializers.ChoiceField(choices=Ticket.Priority.choices, required=False)
    search = serializers.CharField(max_length=100, required=False)


class TicketAssignSerializer(serializers.Serializer):
    """Assign a ticket to an active support agent."""

    agent_id = serializers.PrimaryKeyRelatedField(source="agent", queryset=User.objects.filter(role=User.Role.AGENT, is_active=True))


class TicketStatusSerializer(serializers.Serializer):
    """Requested new status."""

    status = serializers.ChoiceField(choices=Ticket.Status.choices)


class CommentWriteSerializer(serializers.Serializer):
    """Comment text for create and update."""

    body = serializers.CharField(max_length=5000)


class CommentSerializer(serializers.ModelSerializer):
    """A comment as returned to readers of the ticket."""

    author_email = serializers.EmailField(source="author.email", read_only=True, allow_null=True)

    class Meta:
        model = TicketComment
        fields = ("id", "body", "author_email", "created_at", "updated_at")
        read_only_fields = fields
