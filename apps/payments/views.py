from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import (
    TemplateView, CreateView, UpdateView, ListView, DetailView
)
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.conf import settings
from django.db.models import Q, Sum
from decimal import Decimal
import json
import logging

from .models import Payment, Transaction, Invoice, PaymentMethod
from .forms import (
    PaymentForm, PaymentIntentForm, RefundForm, InvoiceForm,
    PaymentMethodForm, PaymentSearchForm
)
from .services import (
    StripePaymentService, PaymentService, PaymentMethodService
)
from apps.doctors.models import Doctor, Appointment

logger = logging.getLogger(__name__)


class PaymentListView(LoginRequiredMixin, ListView):
    """
    List all payments for the authenticated user.
    """
    model = Payment
    template_name = 'payments/list.html'
    context_object_name = 'payments'
    paginate_by = 20
    login_url = reverse_lazy('login')
    
    def get_queryset(self):
        queryset = Payment.objects.filter(patient=self.request.user)
        
        # Apply search and filters
        search_form = PaymentSearchForm(self.request.GET)
        if search_form.is_valid():
            search = search_form.cleaned_data.get('search')
            status = search_form.cleaned_data.get('status')
            payment_type = search_form.cleaned_data.get('payment_type')
            date_from = search_form.cleaned_data.get('date_from')
            date_to = search_form.cleaned_data.get('date_to')
            
            if search:
                queryset = queryset.filter(
                    Q(payment_reference__icontains=search) |
                    Q(description__icontains=search) |
                    Q(doctor__first_name__icontains=search) |
                    Q(doctor__last_name__icontains=search)
                )
            
            if status:
                queryset = queryset.filter(status=status)
            
            if payment_type:
                queryset = queryset.filter(payment_type=payment_type)
            
            if date_from:
                queryset = queryset.filter(created_at__date__gte=date_from)
            
            if date_to:
                queryset = queryset.filter(created_at__date__lte=date_to)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['search_form'] = PaymentSearchForm(self.request.GET)
        context['total_payments'] = self.get_queryset().aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        return context


class PaymentDetailView(LoginRequiredMixin, DetailView):
    """
    Display payment details.
    """
    model = Payment
    template_name = 'payments/detail.html'
    context_object_name = 'payment'
    login_url = reverse_lazy('login')
    
    def get_queryset(self):
        return Payment.objects.filter(patient=self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        payment = self.object
        
        # Get related transactions
        context['transactions'] = payment.transactions.order_by('-processed_at')
        
        # Get refund form if payment can be refunded
        if payment.can_be_refunded:
            context['refund_form'] = RefundForm(payment=payment)
        
        return context


class CreatePaymentView(LoginRequiredMixin, TemplateView):
    """
    Create a new payment for an appointment.
    """
    template_name = 'payments/create.html'
    login_url = reverse_lazy('login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get appointment from URL parameter
        appointment_id = self.kwargs.get('appointment_id')
        if appointment_id:
            try:
                appointment = Appointment.objects.get(
                    id=appointment_id,
                    patient=self.request.user
                )
                context['appointment'] = appointment
                context['amount'] = appointment.doctor.consultation_fee
            except Appointment.DoesNotExist:
                messages.error(self.request, 'Appointment not found.')
                return redirect('users:my_appointments')
        
        context['form'] = PaymentIntentForm()
        context['stripe_publishable_key'] = settings.STRIPE_PUBLISHABLE_KEY
        
        return context
    
    def post(self, request, *args, **kwargs):
        appointment_id = self.kwargs.get('appointment_id')
        if not appointment_id:
            return JsonResponse({'error': 'Appointment ID required'}, status=400)
        
        try:
            appointment = Appointment.objects.get(
                id=appointment_id,
                patient=request.user
            )
        except Appointment.DoesNotExist:
            return JsonResponse({'error': 'Appointment not found'}, status=404)
        
        # Create payment record
        payment = PaymentService.create_appointment_payment(appointment)
        
        # MIMIC PAYMENT: Skip real Stripe and succeed immediately
        import uuid
        payment.stripe_payment_intent_id = f"mimic_{uuid.uuid4().hex}"
        payment.status = 'succeeded'
        payment.paid_at = timezone.now()
        payment.save()
        
        # Update appointment
        appointment.is_paid = True
        appointment.save(update_fields=['is_paid'])
        
        # Create transaction record
        Transaction.objects.create(
            payment=payment,
            transaction_type='payment',
            amount=payment.amount,
            currency=payment.currency,
            external_reference=payment.stripe_payment_intent_id,
            description=f'Simulated payment succeeded for {payment.payment_reference}'
        )
        
        return JsonResponse({
            'success': True,
            'payment_id': str(payment.id),
            'redirect_url': f"{reverse('payments:success')}?payment_id={payment.id}"
        })


@method_decorator(csrf_exempt, name='dispatch')
class PaymentWebhookView(TemplateView):
    """
    Handle Stripe webhook events.
    """
    
    def post(self, request, *args, **kwargs):
        import stripe
        
        payload = request.body
        sig_header = request.META.get('HTTP_STRIPE_SIGNATURE')
        endpoint_secret = settings.STRIPE_WEBHOOK_SECRET
        
        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, endpoint_secret
            )
        except ValueError:
            # Invalid payload
            logger.error('Invalid payload in webhook')
            return HttpResponse(status=400)
        except stripe.error.SignatureVerificationError:
            # Invalid signature
            logger.error('Invalid signature in webhook')
            return HttpResponse(status=400)
        
        # Handle the event
        if event['type'] == 'payment_intent.succeeded':
            self._handle_payment_succeeded(event['data']['object'])
        elif event['type'] == 'payment_intent.payment_failed':
            self._handle_payment_failed(event['data']['object'])
        else:
            logger.info(f'Unhandled event type: {event["type"]}')
        
        return HttpResponse(status=200)
    
    def _handle_payment_succeeded(self, payment_intent):
        """
        Handle successful payment intent.
        """
        try:
            payment = Payment.objects.get(
                stripe_payment_intent_id=payment_intent['id']
            )
            
            # Update payment status
            payment.status = 'succeeded'
            payment.save()
            
            # Update appointment
            payment.appointment.is_paid = True
            payment.appointment.save(update_fields=['is_paid'])
            
            # Create transaction record
            Transaction.objects.create(
                payment=payment,
                transaction_type='payment',
                amount=payment.amount,
                currency=payment.currency,
                external_reference=payment_intent['id'],
                description=f'Payment succeeded for {payment.payment_reference}',
                metadata={
                    'stripe_status': payment_intent['status'],
                    'webhook_processed': True,
                }
            )
            
            logger.info(f'Payment succeeded: {payment.payment_reference}')
            
        except Payment.DoesNotExist:
            logger.error(f'Payment not found for intent: {payment_intent["id"]}')
    
    def _handle_payment_failed(self, payment_intent):
        """
        Handle failed payment intent.
        """
        try:
            payment = Payment.objects.get(
                stripe_payment_intent_id=payment_intent['id']
            )
            
            payment.status = 'failed'
            payment.save()
            
            logger.info(f'Payment failed: {payment.payment_reference}')
            
        except Payment.DoesNotExist:
            logger.error(f'Payment not found for intent: {payment_intent["id"]}')


class PaymentSuccessView(LoginRequiredMixin, TemplateView):
    """
    Payment success page.
    """
    template_name = 'payments/success.html'
    login_url = reverse_lazy('login')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        payment_id = self.request.GET.get('payment_id')
        if payment_id:
            try:
                payment = Payment.objects.get(
                    id=payment_id,
                    patient=self.request.user
                )
                context['payment'] = payment
            except Payment.DoesNotExist:
                messages.error(self.request, 'Payment not found.')
        
        return context


class PaymentCancelView(LoginRequiredMixin, TemplateView):
    """
    Payment cancellation page.
    """
    template_name = 'payments/cancel.html'
    login_url = reverse_lazy('login')


@login_required
@require_POST
def process_refund(request, payment_id):
    """
    Process a payment refund.
    """
    payment = get_object_or_404(Payment, id=payment_id, patient=request.user)
    
    if not payment.can_be_refunded:
        messages.error(request, 'This payment cannot be refunded.')
        return redirect('payments:detail', pk=payment.id)
    
    form = RefundForm(payment=payment, data=request.POST)
    if form.is_valid():
        refund_amount = form.cleaned_data.get('refund_amount')
        reason = form.cleaned_data.get('reason')
        notes = form.cleaned_data.get('notes')
        
        # Process refund
        success = PaymentService.process_refund(
            payment=payment,
            refund_amount=refund_amount,
            reason=f"{reason}: {notes}" if notes else reason
        )
        
        if success:
            messages.success(request, 'Refund processed successfully.')
        else:
            messages.error(request, 'Failed to process refund. Please try again.')
    else:
        messages.error(request, 'Please correct the form errors.')
    
    return redirect('payments:detail', pk=payment.id)


class PaymentMethodListView(LoginRequiredMixin, ListView):
    """
    List user's saved payment methods.
    """
    template_name = 'payments/payment_methods.html'
    context_object_name = 'payment_methods'
    login_url = reverse_lazy('login')
    
    def get_queryset(self):
        return PaymentMethodService.get_user_payment_methods(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['form'] = PaymentMethodForm()
        context['stripe_publishable_key'] = settings.STRIPE_PUBLISHABLE_KEY
        return context


@login_required
def payment_method_create(request):
    """
    Save a new payment method.
    """
    if request.method == 'POST':
        stripe_payment_method_id = request.POST.get('payment_method_id')
        is_default = request.POST.get('set_default') == 'on'
        
        if stripe_payment_method_id:
            payment_method = PaymentMethodService.save_payment_method(
                user=request.user,
                stripe_payment_method_id=stripe_payment_method_id,
                is_default=is_default
            )
            
            if payment_method:
                messages.success(request, 'Payment method saved successfully.')
            else:
                messages.error(request, 'Failed to save payment method.')
        else:
            messages.error(request, 'Payment method ID is required.')
    
    return redirect('payments:payment_methods')


@login_required
@require_POST
def set_default_payment_method(request, method_id):
    """
    Set a payment method as default.
    """
    success = PaymentMethodService.set_default_payment_method(
        user=request.user,
        payment_method_id=method_id
    )
    
    if success:
        messages.success(request, 'Default payment method updated.')
    else:
        messages.error(request, 'Failed to update default payment method.')
    
    return redirect('payments:payment_methods')


class InvoiceListView(LoginRequiredMixin, ListView):
    """
    List invoices for the authenticated user.
    """
    model = Invoice
    template_name = 'payments/invoice_list.html'
    context_object_name = 'invoices'
    paginate_by = 20
    login_url = reverse_lazy('login')
    
    def get_queryset(self):
        return Invoice.objects.filter(
            appointment__patient=self.request.user
        ).order_by('-issue_date')


class InvoiceDetailView(LoginRequiredMixin, DetailView):
    """
    Display invoice details.
    """
    model = Invoice
    template_name = 'payments/invoice_detail.html'
    context_object_name = 'invoice'
    login_url = reverse_lazy('login')
    
    def get_queryset(self):
        return Invoice.objects.filter(appointment__patient=self.request.user)


class DoctorPaymentDashboardView(LoginRequiredMixin, TemplateView):
    """
    Payment dashboard for doctors.
    """
    template_name = 'payments/doctor_dashboard.html'
    login_url = reverse_lazy('users:login')
    
    def test_func(self):
        return hasattr(self.request.user, 'doctor_profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        doctor = self.request.user.doctor_profile
        
        # Payment statistics
        payments = Payment.objects.filter(doctor=doctor)
        context['total_earnings'] = payments.filter(
            status='succeeded'
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        context['pending_payments'] = payments.filter(
            status__in=['pending', 'processing']
        ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        
        context['recent_payments'] = payments.filter(
            status='succeeded'
        ).order_by('-paid_at')[:10]
        
        return context
