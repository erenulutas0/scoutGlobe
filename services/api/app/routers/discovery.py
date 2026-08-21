"""Discovery endpoints: filtered search over percentiles, and role similarity."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from app.db import SessionDep
from app.models import Club, League, Player, PlayerSeasonMetrics
from app.models.metrics import MIN_MINUTES
from app.schemas.discovery import (
    CandidateOut,
    ComparisonOut,
    ComparisonPlayer,
    DifferenceOut,
    DiscoverOut,
    DiscoveryOptions,
    MetricNoteOut,
    MetricOption,
    PlayerRadar,
    RisingOut,
    RisingPlayer,
    RisingScoreOut,
    SimilarPlayer,
    SimilarPlayersOut,
    ValueMomentumOut,
)
from app.services.discovery import (
    MAX_COMPARE,
    METRIC_LABELS,
    Candidate,
    compare,
    default_season,
    differences,
    discover,
    metrics_for,
    radar,
    rising,
    seasons_for,
    similar_players,
    strengths,
    value_momentum,
    weaknesses,
)
from app.services.players import to_player_summary

router = APIRouter(prefix="/discover", tags=["discover"])

POSITION_GROUPS = ("GK", "DF", "MF", "FW")

# What a keeper percentile can and cannot claim. Said once, here, so every
# goalkeeper response carries the same caveat.
GK_CAVEAT = (
    "Kaleci sıralaması kurtarış, kurtarış oranı, yenen gol ve gol yememe üzerinden. "
    "PSxG (şut sonrası beklenen gol) hiçbir kaynağımızda yok, yani karşılaştığı şutun "
    "zorluğunu ölçemiyoruz: az gol yemek iyi bir savunmanın önünde durmakla da olur."
)

# What a tackle count can and cannot say. Volume metrics reward the defender who
# is forced to defend: van Dijk sits in the 4th percentile for tackles won and
# the 15th for interceptions because he is rarely out of position, while a
# centre-back on a team under siege makes both all afternoon. Possession-
# adjusted numbers would fix this and no source here publishes them.
DEFENSIVE_CAVEAT = (
    "Araya girme ve müdahale sayıları hacimdir, kalite değil: pozisyonunu bozmayan "
    "bir stoper az müdahale eder, sürekli savunan bir takımınki çok. Topa sahip olma "
    "oranına göre düzeltilmiş sayılar bunu çözerdi, hiçbir kaynağımızda yok."
)

# Similarity is a different matter. The role vector's seven axes are all
# shooting, creation and discipline, so a keeper's would describe him by what
# he never does. Keeper similarity needs its own axes and its own space.
GK_SIMILAR_NOTE = (
    "Kaleci benzerliği henüz yok: rol vektörünün eksenleri şut ve üretim, "
    "yani bir kaleciyi hiç yapmadığı şeylerle tarif ederdi."
)


def to_candidate(candidate: Candidate) -> CandidateOut:
    return CandidateOut(
        player=to_player_summary(
            candidate.player,
            club_name=candidate.club.name if candidate.club else None,
            league_id=candidate.league.id if candidate.league else None,
        ),
        season=candidate.metrics.season,
        position_group=candidate.metrics.position_group,
        minutes=candidate.metrics.minutes,
        club_name=candidate.club.name if candidate.club else None,
        league_id=candidate.league.id if candidate.league else None,
        league_name=candidate.league.name if candidate.league else None,
        league_tier=candidate.league.tier if candidate.league else None,
        strengths=[MetricNoteOut.model_validate(note) for note in strengths(candidate.metrics)],
        weaknesses=[MetricNoteOut.model_validate(note) for note in weaknesses(candidate.metrics)],
    )


@router.get("/options", response_model=DiscoveryOptions, summary="Keşif formunun seçenekleri")
def discovery_options(session: SessionDep) -> DiscoveryOptions:
    """Seasons, position groups and metrics the form may offer.

    Coverage travels with each metric: xG exists for five leagues out of twelve,
    and a form that offers it without saying so would quietly narrow a search to
    a fraction of the database.
    """
    seasons = list(
        session.scalars(
            select(PlayerSeasonMetrics.season).distinct().order_by(PlayerSeasonMetrics.season.desc())
        ).all()
    )

    counts = dict(
        session.execute(
            select(
                func.jsonb_object_keys(PlayerSeasonMetrics.percentile).label("metric"),
                func.count(),
            ).group_by("metric")
        ).all()
    )
    metrics = [
        MetricOption(metric=metric, label=label, coverage=counts.get(metric, 0))
        for metric, label in METRIC_LABELS.items()
        if counts.get(metric, 0)
    ]
    metrics.sort(key=lambda option: option.coverage, reverse=True)

    return DiscoveryOptions(
        seasons=seasons,
        position_groups=list(POSITION_GROUPS),
        metrics=metrics,
        min_minutes=MIN_MINUTES,
    )


@router.get("", response_model=DiscoverOut, summary="Kritere uyan oyuncuları bul")
def discover_players(
    session: SessionDep,
    position_group: str = Query(..., description="GK / DF / MF / FW"),
    season: str | None = Query(None, description="Varsayılan: en güncel sezon"),
    metric: str | None = Query(None, description="Sıralanacak metrik; boşsa en güçlü yönüne göre"),
    min_percentile: float = Query(0.70, ge=0.0, le=1.0),
    max_value_eur: float | None = Query(None, ge=0, description="Bütçe tavanı (EUR)"),
    max_age: int | None = Query(None, ge=14, le=45),
    league_id: Annotated[list[int] | None, Query(description="Şu an oynadığı lig")] = None,
    min_minutes: int = Query(MIN_MINUTES, ge=MIN_MINUTES, description="900'ün altı yanıltıcıdır"),
    limit: int = Query(25, ge=1, le=100),
) -> DiscoverOut:
    group = position_group.upper()
    if group not in POSITION_GROUPS:
        raise HTTPException(
            status_code=400, detail=f"position_group {POSITION_GROUPS} icinden biri olmali"
        )
    if metric and metric not in METRIC_LABELS:
        raise HTTPException(status_code=400, detail=f"Bilinmeyen metrik: {metric}")

    resolved = season or default_season(session)
    if resolved is None:
        return DiscoverOut(
            season="", position_group=group, metric=metric, note="Henüz metrik hesaplanmadı."
        )

    found = discover(
        session,
        season=resolved,
        position_group=group,
        metric=metric,
        min_percentile=min_percentile,
        max_value_eur=max_value_eur,
        max_age=max_age,
        league_ids=league_id,
        min_minutes=min_minutes,
        limit=limit,
    )

    if not found:
        note = "Bu filtrelere uyan oyuncu yok. Persentil eşiğini veya bütçeyi gevşetmeyi dene."
    elif group == "GK":
        note = GK_CAVEAT
    elif group in ("DF", "MF"):
        note = DEFENSIVE_CAVEAT
    else:
        note = None
    return DiscoverOut(
        season=resolved,
        position_group=group,
        metric=metric,
        items=[to_candidate(candidate) for candidate in found],
        note=note,
    )


@router.get(
    "/similar/{player_id}",
    response_model=SimilarPlayersOut,
    summary="Rol profili benzeyen oyuncular",
)
def similar(
    session: SessionDep,
    player_id: int,
    season: str | None = Query(None, description="Varsayılan: oyuncunun en son sezonu"),
    max_value_eur: float | None = Query(None, ge=0, description="Bütçe tavanı (EUR)"),
    max_age: int | None = Query(None, ge=14, le=45),
    league_id: Annotated[list[int] | None, Query(description="Şu an oynadığı lig")] = None,
    limit: int = Query(10, ge=1, le=50),
) -> SimilarPlayersOut:
    player = session.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Oyuncu bulunamadı")

    reference = metrics_for(session, player_id, season)
    if reference is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{player.full_name} için {MIN_MINUTES} dakikayı geçen bir sezon yok, "
                "bu yüzden karşılaştırılabilir bir profili de yok."
            ),
        )

    club = session.get(Club, player.current_club_id) if player.current_club_id else None
    reference_candidate = Candidate(
        player=player,
        metrics=reference,
        club=club,
        league=session.get(League, club.league_id) if club and club.league_id else None,
    )

    if reference.position_group == "GK":
        return SimilarPlayersOut(
            reference=to_candidate(reference_candidate), note=GK_SIMILAR_NOTE
        )

    found = similar_players(
        session,
        reference,
        limit=limit,
        max_value_eur=max_value_eur,
        max_age=max_age,
        league_ids=league_id,
    )

    items = [
        SimilarPlayer(
            **to_candidate(candidate).model_dump(by_alias=False),
            distance=round(candidate.distance or 0.0, 4),
            differences=[
                DifferenceOut.model_validate(difference)
                for difference in differences(candidate.metrics, reference)
            ],
        )
        for candidate in found
    ]

    note = None
    if not items:
        note = "Bu filtrelerde benzer profil çıkmadı. Bütçeyi veya lig seçimini genişlet."
    return SimilarPlayersOut(
        reference=to_candidate(reference_candidate), items=items, note=note
    )


@router.get(
    "/radar/{player_id}",
    response_model=PlayerRadar,
    summary="Oyuncunun pozisyonuna göre persentil profili",
)
def player_radar(
    session: SessionDep,
    player_id: int,
    season: str | None = Query(None, description="Varsayılan: oyuncunun en son sezonu"),
) -> PlayerRadar:
    player = session.get(Player, player_id)
    if player is None:
        raise HTTPException(status_code=404, detail="Oyuncu bulunamadı")

    metrics = metrics_for(session, player_id, season)
    if metrics is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"{player.full_name} için {MIN_MINUTES} dakikayı geçen bir sezon yok, "
                "bu yüzden persentil profili de yok."
            ),
        )

    club = session.get(Club, player.current_club_id) if player.current_club_id else None
    league = session.get(League, metrics.league_id) if metrics.league_id else None
    axes = radar(metrics)

    note = None
    if axes and metrics.position_group in ("DF", "MF"):
        note = DEFENSIVE_CAVEAT
    if not axes:
        note = (
            "Bu sezonda radar çizecek kadar ölçülmüş metrik yok — bir profil en az "
            "üç eksen ister, altındaki bir şekil değil çizgidir."
        )
    if metrics.position_group == "GK" and axes:
        note = GK_CAVEAT

    return PlayerRadar(
        season=metrics.season,
        position_group=metrics.position_group,
        minutes=metrics.minutes,
        league_id=league.id if league else None,
        league_name=league.name if league else None,
        league_tier=league.tier if league else None,
        club_name=club.name if club else None,
        axes=[MetricNoteOut.model_validate(note_) for note_ in axes],
        strengths=[MetricNoteOut.model_validate(n) for n in strengths(metrics)],
        weaknesses=[MetricNoteOut.model_validate(n) for n in weaknesses(metrics)],
        seasons=seasons_for(session, player_id),
        note=note,
    )


@router.get("/rising", response_model=RisingOut, summary="Yükselen oyuncular")
def rising_players(
    session: SessionDep,
    season: str | None = Query(None, description="Varsayılan: en kalabalık sezon"),
    max_age: int = Query(23, ge=16, le=30, description="Bu yaş ve altı"),
    position_group: str | None = Query(None, description="GK / DF / MF / FW"),
    max_value_eur: float | None = Query(None, ge=0, description="Bütçe tavanı (EUR)"),
    league_id: Annotated[list[int] | None, Query(description="Şu an oynadığı lig")] = None,
    limit: int = Query(25, ge=1, le=100),
) -> RisingOut:
    group = position_group.upper() if position_group else None
    if group and group not in POSITION_GROUPS:
        raise HTTPException(
            status_code=400, detail=f"position_group {POSITION_GROUPS} icinden biri olmali"
        )

    resolved = season or default_season(session)
    if resolved is None:
        return RisingOut(season="", max_age=max_age, note="Henüz metrik hesaplanmadı.")

    found = rising(
        session,
        season=resolved,
        max_age=max_age,
        position_group=group,
        max_value_eur=max_value_eur,
        league_ids=league_id,
        limit=limit,
    )

    momentum = value_momentum(session, [candidate.player.id for candidate, _ in found])
    items = [
        RisingPlayer(
            **to_candidate(candidate).model_dump(by_alias=False),
            rising=RisingScoreOut.model_validate(score),
            momentum=(
                ValueMomentumOut.model_validate(momentum[candidate.player.id])
                if candidate.player.id in momentum
                else None
            ),
        )
        for candidate, score in found
    ]

    note = None
    if not items:
        note = "Bu filtrelere uyan genç oyuncu yok. Yaşı veya bütçeyi gevşetmeyi dene."
    return RisingOut(season=resolved, max_age=max_age, items=items, note=note)


@router.get("/compare", response_model=ComparisonOut, summary="Oyuncuları yan yana koy")
def compare_players(
    session: SessionDep,
    player_id: Annotated[
        list[int], Query(description=f"Karşılaştırılacak oyuncular (en fazla {MAX_COMPARE})")
    ],
    season: str | None = Query(None, description="Varsayılan: her oyuncunun en son sezonu"),
) -> ComparisonOut:
    if len(player_id) < 2:
        raise HTTPException(status_code=400, detail="Karşılaştırma en az iki oyuncu ister")

    result = compare(session, player_id, season)

    if not result.players:
        return ComparisonOut(
            note=(
                f"Seçilen oyuncuların {MIN_MINUTES} dakikayı geçen bir sezonu yok, "
                "bu yüzden karşılaştırılacak bir profilleri de yok."
            )
        )

    note = None
    if not result.axes:
        note = (
            "Bu oyuncuların ortak ölçülmüş metriği yok. Genellikle sebebi farklı ligler: "
            "beklenen gol her ligde yayımlanmıyor."
        )
    elif len(result.position_groups) > 1:
        note = (
            "Farklı pozisyon gruplarını karşılaştırıyorsun; persentiller kendi grupları "
            "içinde hesaplandı, yani aynı eksende bile aynı popülasyona bakmıyorlar."
        )

    return ComparisonOut(
        axes=list(result.axes),
        chart_axes=list(result.chart_axes),
        labels=result.labels,
        players=[
            ComparisonPlayer(
                **to_candidate(candidate).model_dump(by_alias=False),
                axes={
                    metric: MetricNoteOut.model_validate(note_)
                    for metric, note_ in values.items()
                },
            )
            for candidate, values in result.players
        ],
        dropped=list(result.dropped),
        dropped_labels=[METRIC_LABELS[metric] for metric in result.dropped],
        position_groups=list(result.position_groups),
        note=note,
    )

