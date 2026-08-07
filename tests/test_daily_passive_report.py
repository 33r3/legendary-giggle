from datetime import date, datetime, timezone

from app.models import PassiveFragmentAward, PassiveTierConfig
from app.status import daily_passive_awards


def make_config(db_session) -> PassiveTierConfig:
    config = PassiveTierConfig(
        floor_steps=1000,
        steps_per_fragment=100,
        daily_cap_fragments=5,
        effective_from=datetime(2020, 1, 1, tzinfo=timezone.utc),
    )
    db_session.add(config)
    db_session.commit()
    db_session.refresh(config)
    return config


def add_award(db_session, config, day, steps, fragments):
    db_session.add(
        PassiveFragmentAward(
            award_date=day, steps_counted=steps, fragments_awarded=fragments, config_id=config.id
        )
    )
    db_session.commit()


def test_daily_passive_awards_returns_everything_oldest_first(db_session):
    config = make_config(db_session)
    add_award(db_session, config, date(2026, 8, 3), 6000, 4)
    add_award(db_session, config, date(2026, 8, 1), 5000, 3)
    add_award(db_session, config, date(2026, 8, 2), 4000, 2)

    awards = daily_passive_awards(db_session)

    assert [a.award_date for a in awards] == [date(2026, 8, 1), date(2026, 8, 2), date(2026, 8, 3)]


def test_daily_passive_awards_filters_by_range(db_session):
    config = make_config(db_session)
    add_award(db_session, config, date(2026, 8, 1), 5000, 3)
    add_award(db_session, config, date(2026, 8, 5), 5000, 3)
    add_award(db_session, config, date(2026, 8, 10), 5000, 3)

    awards = daily_passive_awards(db_session, start=date(2026, 8, 2), end=date(2026, 8, 9))

    assert [a.award_date for a in awards] == [date(2026, 8, 5)]
