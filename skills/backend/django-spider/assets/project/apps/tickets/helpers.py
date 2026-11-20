import logging

from django.db import transaction
from django.db.models import Q, QuerySet
from rest_framework.exceptions import NotFound, PermissionDenied, ValidationError

from apps.accounts.models import User
from apps.tickets.models import Ticket, TicketComment, TicketHistory

logger = logging.getLogger(__name__)


class TicketHelper:
    """Business rules for tickets, their comments and their history."""

    ALLOWED_STATUS_TRANSITIONS = {
        Ticket.Status.OPEN: {Ticket.Status.IN_PROGRESS, Ticket.Status.CLOSED, Ticket.Status.CANCELLED},
        Ticket.Status.IN_PROGRESS: {Ticket.Status.RESOLVED, Ticket.Status.CLOSED},
        Ticket.Status.RESOLVED: {Ticket.Status.CLOSED},
        Ticket.Status.CLOSED: set(),
        Ticket.Status.CANCELLED: set(),
    }

    @staticmethod
    def get_tickets_for_user(user: User) -> QuerySet[Ticket]:
        """Every ticket query starts here: customers see their own, agents their assigned, admins all."""
        tickets = Ticket.objects.select_related("customer", "assigned_agent")
        if user.role == User.Role.CUSTOMER:
            return tickets.filter(customer=user)
        if user.role == User.Role.AGENT:
            return tickets.filter(assigned_agent=user)
        if user.role == User.Role.ADMINISTRATOR:
            return tickets
        return tickets.none()

    @classmethod
    def get_ticket_for_user(cls, user: User, ticket_id: int, for_update: bool = False) -> Ticket:
        """One ticket the user may see; anything else is reported as missing."""
        tickets = cls.get_tickets_for_user(user)
        if for_update:
            tickets = tickets.select_for_update(of=("self",))
        ticket = tickets.filter(pk=ticket_id).first()
        if ticket is None:
            raise NotFound("Ticket not found.")
        return ticket

    @classmethod
    def list_tickets(cls, user: User, params: dict) -> QuerySet[Ticket]:
        """The user's tickets with the validated filters applied."""
        tickets = cls.get_tickets_for_user(user)
        if params.get("status"):
            tickets = tickets.filter(status=params["status"])
        if params.get("priority"):
            tickets = tickets.filter(priority=params["priority"])
        if params.get("search"):
            tickets = tickets.filter(Q(title__icontains=params["search"]) | Q(description__icontains=params["search"]))
        return tickets

    @staticmethod
    @transaction.atomic
    def create_ticket(customer: User, data: dict) -> Ticket:
        """Create a ticket and its first history row together."""
        ticket = Ticket.objects.create(customer=customer, **data)
        TicketHistory.objects.create(ticket=ticket, changed_by=customer, action=TicketHistory.Action.CREATED, new_value=ticket.status)
        logger.info("Ticket created | ticket_id=%s | customer_id=%s", ticket.id, customer.id)
        return ticket

    @classmethod
    @transaction.atomic
    def assign_ticket(cls, ticket_id: int, agent: User, changed_by: User) -> Ticket:
        """Assign an open ticket to an agent (administrators only, checked by the view's permission)."""
        ticket = cls.get_ticket_for_user(changed_by, ticket_id, for_update=True)
        if ticket.status in {Ticket.Status.CLOSED, Ticket.Status.CANCELLED}:
            raise ValidationError("Closed or cancelled tickets cannot be assigned.")
        previous_agent_id = ticket.assigned_agent_id
        if previous_agent_id == agent.id:
            return ticket
        ticket.assigned_agent = agent
        ticket.save(update_fields=["assigned_agent", "updated_at"])
        TicketHistory.objects.create(ticket=ticket, changed_by=changed_by, action=TicketHistory.Action.ASSIGNED, old_value=str(previous_agent_id or ""), new_value=str(agent.id))
        logger.info("Ticket assigned | ticket_id=%s | agent_id=%s | changed_by_id=%s", ticket.id, agent.id, changed_by.id)
        return ticket

    @classmethod
    @transaction.atomic
    def change_status(cls, ticket_id: int, new_status: str, changed_by: User) -> Ticket:
        """Move a ticket along the allowed transitions; customers may only cancel."""
        ticket = cls.get_ticket_for_user(changed_by, ticket_id, for_update=True)
        if changed_by.role == User.Role.CUSTOMER and new_status != Ticket.Status.CANCELLED:
            raise PermissionDenied("Customers can only cancel their tickets.")
        if new_status not in cls.ALLOWED_STATUS_TRANSITIONS[ticket.status]:
            raise ValidationError(f"A ticket cannot move from {ticket.status} to {new_status}.")
        old_status = ticket.status
        ticket.status = new_status
        ticket.save(update_fields=["status", "updated_at"])
        TicketHistory.objects.create(ticket=ticket, changed_by=changed_by, action=TicketHistory.Action.STATUS_CHANGED, old_value=old_status, new_value=new_status)
        logger.info("Ticket status changed | ticket_id=%s | from=%s | to=%s | changed_by_id=%s", ticket.id, old_status, new_status, changed_by.id)
        return ticket

    @classmethod
    def list_comments(cls, user: User, ticket_id: int) -> QuerySet[TicketComment]:
        """Comments of a ticket the user may see."""
        ticket = cls.get_ticket_for_user(user, ticket_id)
        return ticket.comments.select_related("author")

    @classmethod
    def add_comment(cls, user: User, ticket_id: int, body: str) -> TicketComment:
        """Comment on a ticket the user may see."""
        ticket = cls.get_ticket_for_user(user, ticket_id)
        comment = TicketComment.objects.create(ticket=ticket, author=user, body=body)
        logger.info("Comment added | ticket_id=%s | comment_id=%s | user_id=%s", ticket.id, comment.id, user.id)
        return comment

    @classmethod
    def get_own_comment(cls, user: User, ticket_id: int, comment_id: int) -> TicketComment:
        """A comment on a visible ticket that the user wrote; only authors may change it."""
        comment = cls.list_comments(user, ticket_id).filter(pk=comment_id).first()
        if comment is None:
            raise NotFound("Comment not found.")
        if comment.author_id != user.id:
            raise PermissionDenied("Only the author can change this comment.")
        return comment

    @classmethod
    def update_comment(cls, user: User, ticket_id: int, comment_id: int, body: str) -> TicketComment:
        """Edit the user's own comment."""
        comment = cls.get_own_comment(user, ticket_id, comment_id)
        comment.body = body
        comment.save(update_fields=["body", "updated_at"])
        logger.info("Comment updated | comment_id=%s | user_id=%s", comment.id, user.id)
        return comment

    @classmethod
    def delete_comment(cls, user: User, ticket_id: int, comment_id: int) -> None:
        """Delete the user's own comment."""
        comment = cls.get_own_comment(user, ticket_id, comment_id)
        comment.delete()
        logger.info("Comment deleted | comment_id=%s | user_id=%s", comment_id, user.id)
