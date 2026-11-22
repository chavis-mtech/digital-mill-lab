"""Service metadata. Owner: architect (implemented)."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.v1._contract import contract
from app.config import PRODUCT_NAME, PRODUCT_TAGLINE, Settings, get_settings
from app.schemas.common import Disclaimer
from app.schemas.meta import DataWindow, MetaResponse

router = APIRouter(tags=["meta"])

DISCLAIMERS = [
    Disclaimer(
        key="independent_concept",
        text_en="Independent portfolio / concept demo. Not an official system of any company and not affiliated with or endorsed by any company.",
        text_th="โครงการแนวคิดอิสระเพื่อการนำเสนอผลงาน ไม่ใช่ระบบทางการของบริษัทใด ๆ และไม่ได้รับการรับรองจากบริษัทใด ๆ",
    ),
    Disclaimer(
        key="synthetic_data",
        text_en="All plant, supplier and production data are synthetic (deterministically generated). No internal company data is used.",
        text_th="ข้อมูลโรงงาน ผู้ส่งวัตถุดิบ และการผลิตทั้งหมดเป็นข้อมูลสังเคราะห์ ไม่มีการใช้ข้อมูลภายในของบริษัทใด",
    ),
    Disclaimer(
        key="simulated_live",
        text_en="'Simulated Live' replays synthetic data; it is not a live plant feed.",
        text_th="โหมด 'Simulated Live' เป็นการจำลองด้วยข้อมูลสังเคราะห์ ไม่ใช่ข้อมูลสดจากโรงงานจริง",
    ),
    Disclaimer(
        key="advisory_ai",
        text_en="AI outputs are advisory and read-only. AI never controls machines; humans confirm any change to business records.",
        text_th="ผลลัพธ์ AI เป็นเพียงคำแนะนำ ไม่ควบคุมเครื่องจักร และต้องมีการยืนยันโดยมนุษย์ก่อนแก้ไขข้อมูลทางธุรกิจ",
    ),
    Disclaimer(
        key="roi_illustrative",
        text_en="Illustrative business scenario based on adjustable assumptions, not verified financial results of any company.",
        text_th="สถานการณ์ทางธุรกิจเพื่อการอธิบาย อิงสมมติฐานที่ปรับได้ ไม่ใช่ผลประกอบการที่ได้รับการตรวจสอบของบริษัทใด ๆ",
    ),
    Disclaimer(
        key="simulated_roles",
        text_en="Roles are simulated viewpoints for the demo, not production authentication.",
        text_th="บทบาทผู้ใช้เป็นมุมมองจำลองสำหรับเดโม ไม่ใช่ระบบยืนยันตัวตนจริง",
    ),
]


@router.get("/meta", response_model=MetaResponse, summary="Product name, disclaimers, version, data window, anchor date",
            openapi_extra=contract(None, "architect", "DML-011", status="implemented"))
def get_meta(settings: Settings = Depends(get_settings)) -> MetaResponse:
    return MetaResponse(
        product=PRODUCT_NAME,
        tagline=PRODUCT_TAGLINE,
        version=settings.version,
        environment=settings.app_env,
        demo_mode=settings.demo_mode,
        data_window=DataWindow(
            start_date=settings.window_start_date,
            end_date=settings.demo_anchor,
            days=settings.dataset_days,
            start_utc=settings.window_start,
            end_utc_exclusive=settings.window_end,
            timezone=settings.mill_timezone,
        ),
        anchor_date=settings.demo_anchor,
        default_as_of=settings.default_as_of,
        copilot_mode="llm" if settings.llm_enabled else "deterministic",
        disclaimers=DISCLAIMERS,
    )
