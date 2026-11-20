from django.contrib import admin

from apps.tickets.models import Ticket, TicketComment, TicketHistory


@admin.register(Ticket)
class TicketAdmin(admin.ModelAdmin):
    """Tickets in the Django admin."""

    list_display = ("id", "title", "status", "priority", "customer", "assigned_agent", "created_at")
    list_filter = ("status", "priority")
    search_fields = ("title", "description")


admin.site.register(TicketComment)
admin.site.register(TicketHistory)
