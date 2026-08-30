import json
import os
import pytest
from src.core.schemas import (
    RawAdRecord,
    AdOfferDetails,
    OfferMatrixSummary,
    HookItem,
    HookAnalysisReport,
)
from src.core.fetcher import fetch_ads
from src.core.extractor import extract_offer_details, build_offer_matrix
from src.core.classifier import (
    detect_language,
    extract_raw_hook,
    classify_single_hook,
    analyze_hooks,
)


# ==============================================================================
# 1. Mock Ads Seed Dataset Schema Validation Tests
# ==============================================================================

def test_mock_ads_json_strict_schema_validation():
    """Verify that every record in mock_ads.json strictly conforms to RawAdRecord."""
    data_path = os.path.join(
        os.path.dirname(__file__), "..", "src", "data", "mock_ads.json"
    )
    assert os.path.exists(data_path), f"mock_ads.json not found at {data_path}"

    with open(data_path, "r", encoding="utf-8") as f:
        raw_items = json.load(f)

    assert isinstance(raw_items, list), "mock_ads.json must contain a JSON list"
    assert len(raw_items) > 0, "mock_ads.json should not be empty"

    validated_records = []
    for item in raw_items:
        record = RawAdRecord(**item)
        assert record.ad_id
        assert record.page_name
        assert record.ad_copy
        assert record.media_type in ["image", "video", "carousel", "unknown"]
        assert record.days_active >= 0
        assert record.industry
        assert record.source_type in ["curated_seed", "live_api"]
        validated_records.append(record)

    assert len(validated_records) == len(raw_items)


def test_fetch_ads_integration():
    """Test fetch_ads returns properly instantiated RawAdRecord objects."""
    ads = fetch_ads(use_mock=True)
    assert isinstance(ads, list)
    assert len(ads) > 0
    assert all(isinstance(ad, RawAdRecord) for ad in ads)

    # Filtered fetch
    fashion_ads = fetch_ads(industry="Fashion", use_mock=True)
    assert all(ad.industry.lower() == "fashion" for ad in fashion_ads)


# ==============================================================================
# 2. Deterministic Extractor Unit Tests (with "LocalBrand_PK")
# ==============================================================================

class TestDeterministicExtractor:
    """Targeted unit tests for extractor.py verifying Pakistani commercial parsing."""

    def test_extract_price_and_discount_vernacular(self):
        """Test extraction of PKR price and vernacular discount terms."""
        ad = RawAdRecord(
            ad_id="lb_001",
            page_name="LocalBrand_PK",
            ad_copy="Flat 50% chhoot, fauri rabta karein COD dastiyab hai. Price sirf Rs. 1499!",
            media_type="image",
            cta_raw="SHOP_NOW",
            days_active=5,
            industry="E-Commerce",
        )
        details = extract_offer_details(ad)

        assert details.ad_id == "lb_001"
        assert details.page_name == "LocalBrand_PK"
        assert details.price_mentioned == "Rs. 1499"
        assert details.discount_percentage == 50
        assert details.has_cash_on_delivery is True
        assert details.primary_cta == "Shop Now"
        assert "fauri" in details.detected_intent_words
        assert "chhoot" in details.detected_intent_words
        assert "rabta" in details.detected_intent_words

    def test_extract_pkr_and_muft_delivery(self):
        """Test PKR currency format, zero/muft delivery and WhatsApp CTA."""
        ad = RawAdRecord(
            ad_id="lb_002",
            page_name="LocalBrand_PK",
            ad_copy="Special Deal: PKR 3500 with muft delivery all over Pakistan! Limited stock bachat offer.",
            media_type="video",
            cta_raw="WHATSAPP_MESSAGE",
            days_active=12,
            industry="Retail",
        )
        details = extract_offer_details(ad)

        assert details.price_mentioned == "Rs. 3500"
        assert details.free_delivery_mentioned is True
        assert details.primary_cta == "Send WhatsApp Message"
        assert "limited stock" in details.detected_intent_words
        assert "bachat" in details.detected_intent_words

    def test_cta_normalization_variants(self):
        """Test normalization for various raw Meta CTA values."""
        cta_mappings = [
            ("ORDER_NOW", "Order Now"),
            ("CALL_NOW", "Call Now"),
            ("LEARN_MORE", "Learn More"),
            ("BUY_NOW", "Shop Now"),
            ("SEND_MESSAGE", "Send WhatsApp Message"),
            ("CUSTOM_UNKNOWN_CTA", "Other"),
        ]
        for raw_cta, expected_normalized in cta_mappings:
            ad = RawAdRecord(
                ad_id="lb_cta_test",
                page_name="LocalBrand_PK",
                ad_copy="Standard ad text without offers.",
                cta_raw=raw_cta,
                industry="General",
            )
            details = extract_offer_details(ad)
            assert details.primary_cta == expected_normalized

    def test_build_offer_matrix_aggregation(self):
        """Test aggregated metrics in build_offer_matrix."""
        ads = [
            RawAdRecord(
                ad_id="lb_agg_1",
                page_name="LocalBrand_PK",
                ad_copy="Cash on delivery available. Free delivery on orders over Rs. 2000.",
                cta_raw="SHOP_NOW",
                industry="Fashion",
            ),
            RawAdRecord(
                ad_id="lb_agg_2",
                page_name="LocalBrand_PK",
                ad_copy="Masterclass registration for Rs. 999 only. Fauri rabta karein.",
                cta_raw="SHOP_NOW",
                industry="EdTech",
            ),
            RawAdRecord(
                ad_id="lb_agg_3",
                page_name="LocalBrand_PK",
                ad_copy="Payment on delivery available all across Pakistan.",
                cta_raw="ORDER_NOW",
                industry="Beauty",
            ),
        ]
        summary = build_offer_matrix(ads)

        assert isinstance(summary, OfferMatrixSummary)
        assert summary.total_ads_evaluated == 3
        # 2 out of 3 have COD (lb_agg_1, lb_agg_3) -> 66.7%
        assert summary.cod_prevalence_pct == 66.7
        # 1 out of 3 has free delivery -> 33.3%
        assert summary.free_shipping_prevalence_pct == 33.3
        assert summary.most_common_cta == "Shop Now"
        assert len(summary.records) == 3

    def test_build_offer_matrix_empty_list(self):
        """Test handling of empty ad list in build_offer_matrix."""
        summary = build_offer_matrix([])
        assert summary.total_ads_evaluated == 0
        assert summary.cod_prevalence_pct == 0.0
        assert summary.free_shipping_prevalence_pct == 0.0
        assert summary.most_common_cta == "None"
        assert summary.records == []


# ==============================================================================
# 3. Language & Hook Classifier Unit Tests (with "LocalBrand_PK")
# ==============================================================================

class TestClassifierAndLanguageDetection:
    """Targeted unit tests for classifier.py verifying Pakistani vernacular NLP."""

    def test_detect_language_roman_urdu(self):
        """Test Roman-Urdu classification when colloquial tokens are present."""
        text = "Apna karobar barhayen aur behtareen bachat ka faida uthayein. Fauri rabta karein."
        assert detect_language(text) == "Roman-Urdu"

    def test_detect_language_english(self):
        """Test English classification for pure English copy."""
        text = "Accelerate your digital growth with data-driven performance marketing strategies."
        assert detect_language(text) == "English"

    def test_detect_language_urdu_script(self):
        """Test Urdu script classification (Nastaliq/Arabic range)."""
        text = "پاکستان کا سب سے بڑا آن لائن اسٹور۔ کیش آن ڈلیوری دستیاب ہے۔"
        assert detect_language(text) == "Urdu"

    def test_detect_language_mixed(self):
        """Test Mixed script + Roman-Urdu token combination."""
        text = "ابھی آرڈر کریں! Fauri rabta karein aur apna gift claim karein."
        assert detect_language(text) == "Mixed"

    def test_extract_raw_hook(self):
        """Test extracting the opening 1-2 sentences."""
        multi_sentence_copy = (
            "Kya aap bhi client acquisition se pareshan hain? "
            "LocalBrand_PK laye hain verified ad strategy! "
            "Mazeed maloomat ke liye humein abhi message karein."
        )
        hook = extract_raw_hook(multi_sentence_copy)
        assert "Kya aap bhi client acquisition se pareshan hain?" in hook
        assert "LocalBrand_PK laye hain verified ad strategy!" in hook
        assert "Mazeed maloomat" not in hook

    @pytest.mark.parametrize(
        "hook_text, expected_category",
        [
            ("Kya aap freelancing start karna chahte hain?", "Curiosity / Question"),
            ("Are you struggling to find qualified leads?", "Curiosity / Question"),
            ("Fauri order karein! Limited stock ending soon!", "Urgency / FOMO"),
            ("Hurry! Last chance to claim your spot today.", "Urgency / FOMO"),
            ("Flat 40% off on all items! Sale starts now.", "Direct Offer / Discount"),
            ("Rs. 1999 special deal with free delivery.", "Direct Offer / Discount"),
            ("5,000+ satisfied clients trust LocalBrand_PK.", "Social Proof / Trust"),
            ("100% authentic and verified guarantee.", "Social Proof / Trust"),
            ("Stop wasting ad spend on unoptimized campaigns.", "Problem-Agitation"),
        ],
    )
    def test_classify_single_hook_categories(self, hook_text, expected_category):
        """Test heuristic classification against standard psychological angles."""
        assert classify_single_hook(hook_text) == expected_category

    def test_analyze_hooks_report_generation(self):
        """Test full hook analysis pipeline and aggregation with LocalBrand_PK ads."""
        ads = [
            RawAdRecord(
                ad_id="lb_hook_1",
                page_name="LocalBrand_PK",
                ad_copy="Kya aap online sales barhana chahte hain? Humse rabta karein.",
                industry="Marketing",
            ),
            RawAdRecord(
                ad_id="lb_hook_2",
                page_name="LocalBrand_PK",
                ad_copy="Fauri rabta karein! Aaj hi limited discount hasil karein.",
                industry="Marketing",
            ),
            RawAdRecord(
                ad_id="lb_hook_3",
                page_name="LocalBrand_PK",
                ad_copy="500+ happy clients trust our proven ad funnels.",
                industry="Marketing",
            ),
        ]
        report = analyze_hooks(ads)

        assert isinstance(report, HookAnalysisReport)
        assert report.total_hooks_analyzed == 3
        assert len(report.items) == 3
        assert report.dominant_hook_type in [
            "Curiosity / Question",
            "Urgency / FOMO",
            "Social Proof / Trust",
            "Direct Offer / Discount",
            "Problem-Agitation",
        ]
        assert all(item.page_name == "LocalBrand_PK" for item in report.items)

    def test_analyze_hooks_empty(self):
        """Test analyze_hooks with empty list."""
        report = analyze_hooks([])
        assert report.total_hooks_analyzed == 0
        assert report.dominant_hook_type == "None"
        assert report.dominant_language == "None"
        assert report.items == []


# ==============================================================================
# 4. Kaggle E-Commerce Demand Enricher Unit Tests
# ==============================================================================

class TestKaggleDemandEnricher:
    """Targeted tests for src/core/kaggle_enricher.py."""

    def test_load_kaggle_demand_returns_top_10(self):
        """Verify load_kaggle_demand returns top 10 categories with positive counts."""
        from src.core.kaggle_enricher import load_kaggle_demand
        demand = load_kaggle_demand()
        assert isinstance(demand, dict)
        assert len(demand) == 10
        assert all(isinstance(k, str) for k in demand.keys())
        assert all(isinstance(v, int) and v > 0 for v in demand.values())

    def test_get_demand_context_fashion(self):
        """Verify get_demand_context formats a descriptive plain English sentence."""
        from src.core.kaggle_enricher import get_demand_context
        ctx = get_demand_context("Fashion")
        assert "Fashion" in ctx or "orders" in ctx
        assert "dataset" in ctx

    def test_get_demand_context_electronics(self):
        """Verify demand context for electronics category."""
        from src.core.kaggle_enricher import get_demand_context
        ctx = get_demand_context("Electronics")
        assert "orders in this dataset" in ctx

    def test_missing_csv_returns_none_and_message(self):
        """Verify load_kaggle_demand returns None and get_demand_context returns missing message when CSV is absent."""
        from src.core.kaggle_enricher import load_kaggle_demand, get_demand_context
        res = load_kaggle_demand(csv_path="non_existent_path.csv")
        assert res is None
        ctx = get_demand_context("Fashion", csv_path="non_existent_path.csv")
        assert ctx == "Kaggle data not loaded — run download command"


# ==============================================================================
# 5. Desktop Application Unit Tests
# ==============================================================================

class TestDesktopApp:
    """Targeted tests for src/desktop/main_window.py."""

    def test_worker_execution(self):
        """Verify AdFetchWorker fetches ads and calculates pipeline metrics including brief."""
        from src.desktop.main_window import AdFetchWorker
        worker = AdFetchWorker(industry="General", use_mock=True)

        results = []
        worker.results_ready.connect(lambda ads, offers, hooks, brief: results.append((ads, offers, hooks, brief)))
        worker.run()

        assert len(results) == 1
        ads, offers, hooks, brief = results[0]
        assert len(ads) > 0
        assert hasattr(offers, "cod_prevalence_pct")
        assert hasattr(hooks, "dominant_language")
        assert hasattr(brief, "market_whitespace")

    def test_window_metric_cards_and_pages_update(self):
        """Verify AdLensPKWindow initializes pages 2 & 3 and updates them properly."""
        import os
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
        from PyQt6.QtWidgets import QApplication, QFrame
        from src.desktop.main_window import AdLensPKWindow
        from src.core.fetcher import fetch_ads
        from src.core.extractor import build_offer_matrix
        from src.core.classifier import analyze_hooks
        from src.core.ai_engine import generate_tactical_brief

        app = QApplication.instance() or QApplication(["--platform", "offscreen"])
        win = AdLensPKWindow()

        # Verify QFrames exist across pages
        frames = win.findChildren(QFrame)
        assert len(frames) >= 4

        # Simulate pipeline update
        ads = fetch_ads("General", use_mock=True)
        offers = build_offer_matrix(ads)
        hooks = analyze_hooks(ads)
        brief = generate_tactical_brief("General", hooks, offers)
        win._on_report_generated(ads, offers, hooks, brief)

        # 1. Page 0 (Market Overview) assertions
        assert win.val_total_ads.text() == f"{len(ads):,}"
        assert "%" in win.val_cod_rate.text()
        assert win.val_dom_lang.text() != "-"

        # 2. Page 2 (Hook Psychology) assertions
        assert win._hook_report is not None
        assert win.val_dom_hook.text() != "-"
        assert win.hooks_table.rowCount() == len(hooks.items)

        # 3. Page 3 (Strategy Playbook) assertions
        assert win._brief is not None
        assert win.val_brief_niche.text() == brief.target_niche
        assert win.val_brief_whitespace.text() == brief.market_whitespace
        assert win.val_brief_angle.text() == brief.recommended_angle
        assert win.val_brief_offer.text() == brief.recommended_offer_structure
        assert win.hooks_list_widget.count() == len(brief.suggested_hooks)
        assert win.export_button.isEnabled() is True

    def test_scheduler_ingest_with_scraper_and_fallback(self):
        """Verify _ingest_all_industries calls scrape_ads_sync and falls back to mock fetch_ads if empty."""
        from unittest.mock import patch, MagicMock
        from src.core.scheduler import _ingest_all_industries
        from src.core.schemas import RawAdRecord

        mock_scraped = [
            RawAdRecord(
                ad_id="scraped_1",
                page_name="Scraped Brand",
                ad_copy="Flat 50% off. Free delivery nationwide.",
                industry="fashion",
                source_type="curated_seed",
            )
        ]

        # Scenario A: scraper returns ads
        with patch("src.core.scheduler.scrape_ads_sync", return_value=mock_scraped) as mock_scrape, \
             patch("src.core.scheduler.save_ads", return_value=1) as mock_save, \
             patch("src.core.scheduler.fetch_ads") as mock_fetch:
            _ingest_all_industries()
            assert mock_scrape.called
            assert mock_save.called
            assert not mock_fetch.called

        # Scenario B: scraper returns empty list -> falls back to fetch_ads(use_mock=True)
        with patch("src.core.scheduler.scrape_ads_sync", return_value=[]) as mock_scrape, \
             patch("src.core.scheduler.save_ads", return_value=1) as mock_save, \
             patch("src.core.scheduler.fetch_ads", return_value=mock_scraped) as mock_fetch:
            _ingest_all_industries()
            assert mock_scrape.called
            assert mock_fetch.called
            # Verify use_mock=True was passed to fetch_ads
            _, kwargs = mock_fetch.call_args
            assert kwargs.get("use_mock") is True
            assert mock_save.called


