from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode.qr import QrCodeWidget
from reportlab.graphics.shapes import Drawing
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfgen import canvas

from apps.facilities.models import Facility


class Command(BaseCommand):
    help = "Generate a printable facility QR check-in PDF for the patient mobile app."

    def add_arguments(self, parser):
        parser.add_argument("--facility-id", help="Facility UUID.")
        parser.add_argument("--facility-code", help="Facility code, for example FAC0001.")
        parser.add_argument("--output", help="Optional output PDF path.")

    def handle(self, *args, **options):
        facility = self._get_facility(options)
        output_path = self._get_output_path(facility=facility, provided=options.get("output"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload = f"patientflow://checkin/facility?facility_id={facility.id}"
        self._render_pdf(facility=facility, payload=payload, output_path=output_path)
        self.stdout.write(self.style.SUCCESS(f"Generated check-in QR PDF: {output_path}"))
        self.stdout.write(f"QR payload: {payload}")

    def _get_facility(self, options) -> Facility:
        facility_id = options.get("facility_id")
        facility_code = options.get("facility_code")
        if not facility_id and not facility_code:
            raise CommandError("Provide --facility-id or --facility-code.")

        queryset = Facility.objects.select_related("organization", "facility_type")
        facility = queryset.filter(pk=facility_id).first() if facility_id else queryset.filter(code=facility_code).first()
        if facility is None:
            raise CommandError("Facility not found.")
        return facility

    def _get_output_path(self, *, facility: Facility, provided: str | None) -> Path:
        if provided:
            return Path(provided)
        safe_code = facility.code.lower().replace("/", "-").replace(" ", "-")
        return settings.MEDIA_ROOT / "checkin_qr" / f"{safe_code}-checkin-qr.pdf"

    def _render_pdf(self, *, facility: Facility, payload: str, output_path: Path) -> None:
        page_width, page_height = A4
        pdf = canvas.Canvas(str(output_path), pagesize=A4)
        navy = colors.HexColor("#102A43")
        teal = colors.HexColor("#088395")
        muted = colors.HexColor("#475569")
        border = colors.HexColor("#D9E2EC")

        pdf.setFillColor(navy)
        pdf.rect(0, page_height - 72 * mm, page_width, 72 * mm, fill=True, stroke=False)
        pdf.setFillColor(colors.white)
        pdf.setFont("Helvetica-Bold", 22)
        pdf.drawCentredString(page_width / 2, page_height - 28 * mm, facility.name)
        pdf.setFont("Helvetica", 12)
        pdf.drawCentredString(page_width / 2, page_height - 39 * mm, "Patient Mobile Check-in")
        pdf.setFillColor(colors.HexColor("#E6F7F9"))
        pdf.roundRect(56 * mm, page_height - 58 * mm, 98 * mm, 10 * mm, 5 * mm, fill=True, stroke=False)
        pdf.setFillColor(teal)
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawCentredString(page_width / 2, page_height - 54.5 * mm, "SCAN WITH THE PATIENT FLOW MOBILE APP")

        qr_size = 90 * mm
        qr = QrCodeWidget(payload)
        bounds = qr.getBounds()
        qr_width = bounds[2] - bounds[0]
        qr_height = bounds[3] - bounds[1]
        drawing = Drawing(qr_size, qr_size, transform=[qr_size / qr_width, 0, 0, qr_size / qr_height, 0, 0])
        drawing.add(qr)
        qr_x = (page_width - qr_size) / 2
        qr_y = page_height - 170 * mm
        pdf.setStrokeColor(border)
        pdf.roundRect(qr_x - 8 * mm, qr_y - 8 * mm, qr_size + 16 * mm, qr_size + 16 * mm, 6 * mm, stroke=True, fill=False)
        renderPDF.draw(drawing, pdf, qr_x, qr_y)

        pdf.setFillColor(navy)
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawCentredString(page_width / 2, qr_y - 20 * mm, "Arrived for your appointment?")
        pdf.setFont("Helvetica", 11)
        pdf.setFillColor(muted)
        lines = [
            "1. Open the Patient Flow mobile app and sign in.",
            "2. Tap Check-in, then Scan QR Code.",
            "3. Scan this code. Check-in works only for your own eligible appointment.",
            "4. If check-in is too early or unavailable, please contact reception.",
        ]
        y = qr_y - 34 * mm
        for line in lines:
            pdf.drawCentredString(page_width / 2, y, line)
            y -= 8 * mm

        pdf.setFillColor(teal)
        pdf.setFont("Helvetica-Bold", 11)
        pdf.drawCentredString(page_width / 2, 30 * mm, f"Facility code: {facility.code}")
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 8)
        pdf.drawCentredString(page_width / 2, 23 * mm, "This QR code contains no patient data and no reusable token.")

        pdf.showPage()
        pdf.save()
