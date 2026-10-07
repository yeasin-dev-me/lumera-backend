"""Notification templates providing structured text and HTML renderings (ADR-0018)."""
from html import escape
from typing import Any
from django.conf import settings
from .models import Notification

def get_frontend_url() -> str:
    """Return configured public storefront base URL."""
    return getattr(settings, "FRONTEND_URL", "http://localhost:3000").rstrip("/")


def render_html_wrapper(title: str, preheader: str, content_html: str) -> str:
    """Wrap content in a clean, responsive, botanical-themed email layout."""
    site_url = get_frontend_url()
    safe_title = escape(title)
    safe_preheader = escape(preheader)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{safe_title}</title>
  <style>
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; background-color: #F8F9FA; color: #212529; margin: 0; padding: 0; line-height: 1.6; }}
    .container {{ max-width: 600px; margin: 40px auto; background-color: #FFFFFF; border-radius: 12px; overflow: hidden; border: 1px solid #E9ECEF; box-shadow: 0 4px 12px rgba(0,0,0,0.03); }}
    .header {{ background-color: #1A362D; color: #F5F1EB; padding: 28px; text-align: center; }}
    .header h1 {{ margin: 0; font-size: 22px; font-weight: 600; letter-spacing: 0.05em; }}
    .content {{ padding: 36px 32px; }}
    .footer {{ background-color: #F8F9FA; padding: 24px; text-align: center; font-size: 12px; color: #6C757D; border-top: 1px solid #E9ECEF; }}
    .btn {{ display: inline-block; background-color: #1A362D; color: #F5F1EB !important; text-decoration: none; padding: 12px 28px; border-radius: 6px; font-weight: 500; font-size: 14px; margin-top: 20px; }}
    .details-box {{ background-color: #F8F9FA; border-radius: 8px; border: 1px solid #E9ECEF; padding: 18px 20px; margin: 20px 0; }}
    .details-row {{ display: flex; justify-content: space-between; margin-bottom: 8px; font-size: 14px; }}
    .details-label {{ color: #6C757D; }}
    .details-value {{ font-weight: 600; color: #212529; }}
    .badge {{ display: inline-block; padding: 4px 10px; border-radius: 20px; font-size: 12px; font-weight: 600; background-color: #E6F4EA; color: #137333; }}
  </style>
</head>
<body>
  <div style="display:none;font-size:1px;color:#333;line-height:1px;max-height:0px;max-width:0px;opacity:0;overflow:hidden;">
    {safe_preheader}
  </div>
  <div class="container">
    <div class="header">
      <h1>LUMERA</h1>
      <p style="margin: 6px 0 0; font-size: 12px; opacity: 0.85;">Botanical Skincare & Science</p>
    </div>
    <div class="content">
      {content_html}
    </div>
    <div class="footer">
      <p style="margin: 0 0 8px;">Lumera Botanical Laboratories &bull; Wholesale Skincare</p>
      <p style="margin: 0;"><a href="{site_url}" style="color: #1A362D; text-decoration: underline;">Visit Storefront</a> &bull; <a href="{site_url}/account/communication-preferences" style="color: #6C757D; text-decoration: underline;">Communication Preferences</a></p>
    </div>
  </div>
</body>
</html>"""


def render_template(
    event_type: str,
    context: dict[str, Any],
) -> tuple[str, str, str]:
    """Returns (subject, text_body, html_body) for a given domain event."""
    site_url = get_frontend_url()
    order = context.get("order")
    user = context.get("user")
    return_request = context.get("return_request")
    refund = context.get("refund")

    customer_name = escape(
        getattr(order, "shipping_full_name", None)
        or (f"{user.first_name} {user.last_name}".strip() if user else None)
        or "Valued Customer"
    )

    # 1. ORDER PLACED
    if event_type == Notification.EVENT_ORDER_PLACED and order:
        order_num = escape(order.order_number)
        subject = f"Order Confirmation: {order_num}"
        view_url = f"{site_url}/account/orders/{order.public_id}"

        text = (
            f"Hello {customer_name},\n\n"
            f"Thank you for placing order {order_num} with Lumera.\n"
            f"Order Total: {order.total} {order.currency}\n"
            f"Shipping To: {getattr(order, 'shipping_address_line1', '')}, {getattr(order, 'shipping_city', '')}\n\n"
            f"View your order: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Thank you for your order!</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>We have successfully received your wholesale skincare order. Our lab and fulfillment teams are preparing your shipment.</p>
          <div class="details-box">
            <div class="details-row"><span class="details-label">Order Number</span><span class="details-value">{order_num}</span></div>
            <div class="details-row"><span class="details-label">Total Amount</span><span class="details-value">{order.total} {order.currency}</span></div>
            <div class="details-row"><span class="details-label">Payment Status</span><span class="details-value">{order.payment_status.capitalize()}</span></div>
          </div>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">View Order Details</a>
          </div>
        """
        html = render_html_wrapper(subject, f"Your Lumera order {order_num} has been confirmed.", html_content)
        return subject, text, html

    # 2. PAYMENT CONFIRMED
    elif event_type == Notification.EVENT_PAYMENT_CONFIRMED and order:
        order_num = escape(order.order_number)
        subject = f"Payment Confirmed for Order {order_num}"
        view_url = f"{site_url}/account/orders/{order.public_id}"

        text = (
            f"Hello {customer_name},\n\n"
            f"We have received payment for order {order_num}.\n"
            f"Amount Paid: {order.total} {order.currency}\n\n"
            f"View your order: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Payment Confirmed</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Your payment of <strong>{order.total} {order.currency}</strong> for order <strong>{order_num}</strong> has been confirmed.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">Review Order Receipt</a>
          </div>
        """
        html = render_html_wrapper(subject, f"Payment confirmed for order {order_num}.", html_content)
        return subject, text, html

    # 3. PAYMENT FAILED
    elif event_type == Notification.EVENT_PAYMENT_FAILED and order:
        order_num = escape(order.order_number)
        subject = f"Payment Notice: Order {order_num}"
        view_url = f"{site_url}/account/orders/{order.public_id}"

        text = (
            f"Hello {customer_name},\n\n"
            f"The payment attempt for order {order_num} was unsuccessful.\n"
            f"Please visit your account to retry payment: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#D32F2F;">Payment Could Not Be Processed</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>We were unable to complete the transaction for order <strong>{order_num}</strong>.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">Retry Payment</a>
          </div>
        """
        html = render_html_wrapper(subject, f"Payment notice for order {order_num}.", html_content)
        return subject, text, html

    # 4. ORDER PROCESSING
    elif event_type == Notification.EVENT_ORDER_PROCESSING and order:
        order_num = escape(order.order_number)
        subject = f"Your Order {order_num} is Being Prepared"
        view_url = f"{site_url}/account/orders/{order.public_id}"

        text = (
            f"Hello {customer_name},\n\n"
            f"Your order {order_num} has entered processing at our distribution center.\n"
            f"Track progress: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Order is Being Prepared</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Our specialists are carefully packing your botanical skincare formulas for order <strong>{order_num}</strong>.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">Track Order Progress</a>
          </div>
        """
        html = render_html_wrapper(subject, f"Order {order_num} is in preparation.", html_content)
        return subject, text, html

    # 5. ORDER SHIPPED
    elif event_type == Notification.EVENT_ORDER_SHIPPED and order:
        order_num = escape(order.order_number)
        courier = escape(getattr(order, "courier", "") or "Standard Carrier")
        tracking_num = escape(getattr(order, "tracking_number", "") or "N/A")
        tracking_url = getattr(order, "tracking_url", "")
        subject = f"Your Order {order_num} Has Shipped!"
        view_url = f"{site_url}/account/orders/{order.public_id}"

        text = (
            f"Hello {customer_name},\n\n"
            f"Great news! Your order {order_num} has been dispatched.\n"
            f"Courier: {courier}\n"
            f"Tracking Number: {tracking_num}\n"
            + (f"Tracking Link: {tracking_url}\n" if tracking_url else "")
            + f"\nView order: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Your Order Has Shipped!</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Your package is on its way to you.</p>
          <div class="details-box">
            <div class="details-row"><span class="details-label">Order Number</span><span class="details-value">{order_num}</span></div>
            <div class="details-row"><span class="details-label">Courier</span><span class="details-value">{courier}</span></div>
            <div class="details-row"><span class="details-label">Tracking Number</span><span class="details-value">{tracking_num}</span></div>
          </div>
          <div style="text-align: center;">
            <a href="{tracking_url or view_url}" class="btn">Track Delivery</a>
          </div>
        """
        html = render_html_wrapper(subject, f"Order {order_num} has been dispatched.", html_content)
        return subject, text, html

    # 6. ORDER DELIVERED
    elif event_type == Notification.EVENT_ORDER_DELIVERED and order:
        order_num = escape(order.order_number)
        subject = f"Your Order {order_num} Has Been Delivered"
        view_url = f"{site_url}/account/orders/{order.public_id}"

        text = (
            f"Hello {customer_name},\n\n"
            f"Your order {order_num} has been delivered.\n"
            f"Thank you for shopping with Lumera.\n\n"
            f"View order: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Package Delivered</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Carrier records indicate order <strong>{order_num}</strong> has arrived.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">View Order History</a>
          </div>
        """
        html = render_html_wrapper(subject, f"Order {order_num} has arrived.", html_content)
        return subject, text, html

    # 7. ORDER CANCELLED
    elif event_type == Notification.EVENT_ORDER_CANCELLED and order:
        order_num = escape(order.order_number)
        subject = f"Order {order_num} Cancellation Notice"
        view_url = f"{site_url}/account/orders/{order.public_id}"

        text = (
            f"Hello {customer_name},\n\n"
            f"Your order {order_num} has been cancelled.\n"
            f"View order details: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Order Cancellation Notice</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Order <strong>{order_num}</strong> has been cancelled. Any reserved quantities have been released.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">View Order Details</a>
          </div>
        """
        html = render_html_wrapper(subject, f"Order {order_num} cancelled.", html_content)
        return subject, text, html

    # 8. RETURN REQUESTED
    elif event_type == Notification.EVENT_RETURN_REQUESTED and return_request:
        ret_id = str(return_request.public_id)
        subject = "Return Request Received"
        view_url = f"{site_url}/account/returns"

        text = (
            f"Hello {customer_name},\n\n"
            f"We have received your return request #{ret_id[:8]}.\n"
            f"Our team will review the request within 1-2 business days.\n\n"
            f"Check status: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Return Request Received</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Your return request has been submitted for review.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">View Return Status</a>
          </div>
        """
        html = render_html_wrapper(subject, "Return request received.", html_content)
        return subject, text, html

    # 9. RETURN APPROVED
    elif event_type == Notification.EVENT_RETURN_APPROVED and return_request:
        subject = "Return Request Approved"
        view_url = f"{site_url}/account/returns"

        text = (
            f"Hello {customer_name},\n\n"
            f"Your return request has been approved. Please follow the instructions to dispatch items.\n\n"
            f"View instructions: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Return Request Approved</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Your return request has been approved by our quality care department.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">Return Instructions</a>
          </div>
        """
        html = render_html_wrapper(subject, "Return approved.", html_content)
        return subject, text, html

    # 10. RETURN REJECTED
    elif event_type == Notification.EVENT_RETURN_REJECTED and return_request:
        subject = "Return Request Update"
        view_url = f"{site_url}/account/returns"

        text = (
            f"Hello {customer_name},\n\n"
            f"Your return request could not be approved at this time.\n\n"
            f"View details: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Return Request Update</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Your return request could not be approved at this time.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">Review Return Details</a>
          </div>
        """
        html = render_html_wrapper(subject, "Return request status update.", html_content)
        return subject, text, html

    # 11. RETURN RECEIVED
    elif event_type == Notification.EVENT_RETURN_RECEIVED and return_request:
        subject = "Return Items Received"
        view_url = f"{site_url}/account/returns"

        text = (
            f"Hello {customer_name},\n\n"
            f"We have received your returned package at our fulfillment lab.\n\n"
            f"View details: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Returned Items Received</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Your package has been safely received at our facility.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">View Return Status</a>
          </div>
        """
        html = render_html_wrapper(subject, "Returned items received.", html_content)
        return subject, text, html

    # 12. REFUND INITIATED / COMPLETED
    elif event_type in (Notification.EVENT_REFUND_INITIATED, Notification.EVENT_REFUND_COMPLETED) and refund:
        amt = refund.amount
        curr = refund.currency
        subject = f"Refund Update: {amt} {curr}"
        view_url = f"{site_url}/account/orders"

        text = (
            f"Hello {customer_name},\n\n"
            f"A refund of {amt} {curr} has been processed for your account.\n\n"
            f"View order records: {view_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Refund Processed</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>A refund in the amount of <strong>{amt} {curr}</strong> has been issued.</p>
          <div style="text-align: center;">
            <a href="{view_url}" class="btn">View Account Orders</a>
          </div>
        """
        html = render_html_wrapper(subject, f"Refund of {amt} {curr} processed.", html_content)
        return subject, text, html

    # 13. ACCOUNT WELCOME
    elif event_type == Notification.EVENT_ACCOUNT_WELCOME:
        subject = "Welcome to Lumera Botanical Skincare"
        browse_url = f"{site_url}/products"

        text = (
            f"Hello {customer_name},\n\n"
            f"Welcome to Lumera! Your wholesale skincare account has been created.\n"
            f"Explore our botanical catalog: {browse_url}\n\n"
            f"Best regards,\nThe Lumera Team"
        )
        html_content = f"""
          <h2 style="margin-top:0; color:#1A362D;">Welcome to Lumera!</h2>
          <p>Hello <strong>{customer_name}</strong>,</p>
          <p>Your wholesale skincare account is ready. Discover our clinical botanical formulations, barrier restoration creams, and active floral elixirs.</p>
          <div style="text-align: center;">
            <a href="{browse_url}" class="btn">Explore Wholesale Catalog</a>
          </div>
        """
        html = render_html_wrapper(subject, "Welcome to Lumera wholesale skincare.", html_content)
        return subject, text, html

    # Fallback generic update
    subject = "Update regarding your Lumera Account"
    text = f"Hello {customer_name},\n\nThere is an update regarding your Lumera account.\n\nBest regards,\nThe Lumera Team"
    html = render_html_wrapper(subject, "Lumera Account Update", f"<p>Hello <strong>{customer_name}</strong>,</p><p>There is an update regarding your account.</p>")
    return subject, text, html
