from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Literal

from schemas.search_result import SearchResult
from schemas.trl_assessment import TrlAssessment

if TYPE_CHECKING:
    from config import RuntimeConfig


class TrlAnalysisNode:
    """수집된 자료를 바탕으로 기술 성숙도 평가를 생성한다."""

    def __init__(self, config: "RuntimeConfig | None" = None) -> None:
        self._trl_config = config.trl if config is not None else None

    # config 없을 때 사용하는 fallback 키워드 (config와 일치시킴)
    _fallback_keywords: dict[str, tuple[str, ...]] = {
        "patent": ("patent", "uspto", "출원", "특허", "jp", "kr"),
        "academic": ("isscc", "hot chips", "arxiv", "학회", "논문"),
        "hiring": ("linkedin", "recruit", "hiring", "job", "채용", "엔지니어", "수율", "공정", "모집"),
        "partnership": ("partnership", "collaboration", "asml", "amat", "nvidia", "google", "고객사", "협력", "공급망"),
        "ir": ("ir", "earnings", "analyst", "연구 중", "고객사 검증", "양산 준비", "revenue", "매출", "실적"),
    }

    production_keywords: tuple[str, ...] = (
        "양산", "출하", "mass production", "volume production", "shipment", "ramp",
    )

    _indicator_labels: dict[str, str] = {
        "patent": "특허출원",
        "academic": "학술발표(ISSCC·논문)",
        "hiring": "채용공고(제조·공정 엔지니어)",
        "partnership": "파트너십/공급망",
        "ir": "IR/투자자 언급",
    }

    def analyze(
        self,
        search_results: list[SearchResult],
    ) -> dict[str, dict[str, TrlAssessment]]:
        """기술별·기업별 TRL 결과를 중첩 딕셔너리로 반환한다."""
        grouped: dict[str, list[SearchResult]] = defaultdict(list)
        for item in search_results:
            grouped[f"{item['tech']}::{item['company']}"].append(item)

        assessments: dict[str, dict[str, TrlAssessment]] = defaultdict(dict)
        for key, items in grouped.items():
            tech, company = key.split("::", maxsplit=1)

            # P1-1: query 제외, title + content만 사용
            text_blob = " ".join(
                f"{item['title']} {item['content']}".lower() for item in items
            )
            # P1-2: detected와 signal_count를 analyze()에서 한 번만 계산
            detected = {
                ind: self._detect_indicator(text_blob, ind)
                for ind in self._indicator_labels
            }
            signal_count = sum(detected.values())

            detected_str = ", ".join(
                label for ind, label in self._indicator_labels.items() if detected[ind]
            ) or "없음"
            undetected_str = ", ".join(
                label for ind, label in self._indicator_labels.items() if not detected[ind]
            ) or "없음"

            trl, basis, confidence, limitation = self._infer_trl(
                company, items, detected, signal_count
            )
            assessments[tech][company] = TrlAssessment(
                company=company,
                tech=tech,
                trl=trl,
                basis=basis,
                confidence=confidence,
                evidence=[
                    f"{items[0]['published_date']} 기준 최근 검색 결과 {len(items)}건 확보",
                    f"본 보고서는 {company} / {tech}에 대해 긍정·부정·중립 관점 자료를 수집",
                    f"간접지표 5종: 특허출원, 학술발표(ISSCC·논문), 채용공고(제조·공정 엔지니어), 파트너십/공급망, IR/투자자 언급",
                    f"신호 확인({signal_count}개): {detected_str}",
                    f"신호 미확인: {undetected_str}",
                ],
                limitation=limitation,
            )

        return dict(assessments)

    def _infer_trl(
        self,
        company: str,
        items: list[SearchResult],
        detected: dict[str, bool],
        signal_count: int,
    ) -> tuple[int, Literal["confirmed", "estimated"], Literal["high", "medium", "low"], str | None]:
        """전달받은 지표 탐지 결과와 양산 신호를 조합해 TRL과 신뢰도를 결정한다.
        text_blob 재생성 없이 analyze()에서 계산된 detected/signal_count를 그대로 사용한다.
        """
        # ── 1단계: 양산·출하 신호 (TRL 7/8 confirmed) ──────────────────
        production_count = self._count_production_signals(items)
        if production_count > 0:
            trl_confirmed = 8 if production_count >= 2 else 7
            confidence = self._apply_company_disclosure_penalty(company, "high")
            return trl_confirmed, "confirmed", confidence, None

        # ── 2단계: 지표 조합별 규칙 ─────────────────────────────────────
        has_patent = detected.get("patent", False)
        has_academic = detected.get("academic", False)
        has_hiring = detected.get("hiring", False)
        has_ir = detected.get("ir", False)
        has_partnership = detected.get("partnership", False)

        # 논문 + 특허, 채용 없음 → proof-of-concept TRL 3 (confirmed)
        if has_academic and has_patent and not has_hiring:
            confidence = self._apply_company_disclosure_penalty(company, "medium")
            return 3, "confirmed", confidence, None

        # 채용 + IR → 상업적 관심 TRL 6 (estimated)
        if has_hiring and has_ir:
            trl, basis = 6, "estimated"
        # 채용 + 특허 → 엔지니어링 검증 TRL 5 (estimated)
        elif has_hiring and has_patent:
            trl, basis = 5, "estimated"
        # 채용만 → TRL 5 (estimated)
        elif has_hiring:
            trl, basis = 5, "estimated"
        # 파트너십 → TRL 6 (estimated)
        elif has_partnership:
            trl, basis = 6, "estimated"
        # 특허만 → TRL 4 (estimated)
        elif has_patent:
            trl, basis = 4, "estimated"
        # 학회만 → TRL 3 (estimated)
        elif has_academic:
            trl, basis = 3, "estimated"
        # IR만 → TRL 5 (estimated)
        elif has_ir:
            trl, basis = 5, "estimated"
        else:
            trl, basis = 3, "estimated"

        confidence = (
            "high" if signal_count >= 4
            else "medium" if signal_count >= 2
            else "low"
        )
        confidence = self._apply_company_disclosure_penalty(company, confidence)

        limitation = (
            "Samsung의 제한적 공개 정책으로 인해 실제 기술 성숙도와 ±1~2단계 오차가 있을 수 있음"
            if company == "Samsung"
            else "TRL 4~6 구간은 간접지표 기반 추정이며 실제값과 ±1~2단계 오차가 있을 수 있음"
        )
        return trl, basis, confidence, limitation

    def _detect_indicator(self, text_blob: str, indicator_type: str) -> bool:
        """특정 지표 유형의 키워드가 텍스트에 존재하는지 확인한다."""
        if self._trl_config is not None:
            keywords_map: dict[str, list[str]] = {
                "patent": self._trl_config.patent_keywords,
                "academic": self._trl_config.academic_keywords,
                "hiring": self._trl_config.hiring_keywords,
                "partnership": self._trl_config.partnership_keywords,
                "ir": self._trl_config.ir_keywords,
            }
            keywords: list[str] | tuple[str, ...] = keywords_map.get(indicator_type, [])
        else:
            keywords = self._fallback_keywords.get(indicator_type, ())
        return any(kw in text_blob for kw in keywords)

    def _count_production_signals(self, items: list[SearchResult]) -> int:
        """양산·출하 관련 키워드가 몇 개 매칭되는지 반환한다. query 제외."""
        text_blob = " ".join(
            f"{item['title']} {item['content']}".lower() for item in items
        )
        keywords = (
            self._trl_config.production_keywords
            if self._trl_config is not None
            else list(self.production_keywords)
        )
        return sum(1 for kw in keywords if kw in text_blob)

    def _apply_company_disclosure_penalty(
        self,
        company: str,
        confidence: Literal["high", "medium", "low"],
    ) -> Literal["high", "medium", "low"]:
        """공개가 제한적인 회사는 동일 근거에서도 confidence를 한 단계 낮춘다."""
        penalty_enabled = (
            self._trl_config.samsung_confidence_penalty
            if self._trl_config is not None
            else True
        )
        if not penalty_enabled or company != "Samsung":
            return confidence
        if confidence == "high":
            return "medium"
        if confidence == "medium":
            return "low"
        return "low"
