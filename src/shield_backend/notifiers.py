"""Pluggable guardian notification channels (FCM High-Priority, Telegram, Server SMS Fallback)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NotificationDispatchRecord:
    """Audit record of an alert sent to one guardian channel (never contains transcript)."""

    channel: str  # FCM_HIGH_PRIORITY | TELEGRAM | SERVER_SMS_FALLBACK
    elderly_profile_id: str
    guardian_id: str
    target: str
    alert_id: str
    event_type: str
    message: str


@dataclass
class DispatcherHub:
    """Dispatches least-privilege SOS & Anti-Tamper notifications across channels."""

    fcm_dispatches: list[NotificationDispatchRecord] = field(default_factory=list)
    telegram_dispatches: list[NotificationDispatchRecord] = field(default_factory=list)
    sms_dispatches: list[NotificationDispatchRecord] = field(default_factory=list)

    def send_primary_push(
        self,
        guardians: list[dict[str, Any]],
        elderly_profile_id: str,
        alert_id: str,
        event_type: str,
        message: str,
    ) -> list[NotificationDispatchRecord]:
        """Send high-priority FCM (and optional Telegram) pushes to all paired guardians."""
        sent: list[NotificationDispatchRecord] = []
        for g in guardians:
            fcm_rec = NotificationDispatchRecord(
                channel="FCM_HIGH_PRIORITY",
                elderly_profile_id=elderly_profile_id,
                guardian_id=g["guardian_id"],
                target=g["fcm_token"],
                alert_id=alert_id,
                event_type=event_type,
                message=message,
            )
            self.fcm_dispatches.append(fcm_rec)
            sent.append(fcm_rec)

            if g.get("telegram_chat_id"):
                tg_rec = NotificationDispatchRecord(
                    channel="TELEGRAM",
                    elderly_profile_id=elderly_profile_id,
                    guardian_id=g["guardian_id"],
                    target=str(g["telegram_chat_id"]),
                    alert_id=alert_id,
                    event_type=event_type,
                    message=message,
                )
                self.telegram_dispatches.append(tg_rec)
                sent.append(tg_rec)
        return sent

    def send_server_sms_fallback(
        self,
        guardians: list[dict[str, Any]],
        elderly_profile_id: str,
        alert_id: str,
        event_type: str,
        message: str,
    ) -> list[NotificationDispatchRecord]:
        """Trigger server-side SMS gateway fallback when guardians do not ACK in time."""
        sent: list[NotificationDispatchRecord] = []
        for g in guardians:
            sms_rec = NotificationDispatchRecord(
                channel="SERVER_SMS_FALLBACK",
                elderly_profile_id=elderly_profile_id,
                guardian_id=g["guardian_id"],
                target=g["backup_phone_e164"],
                alert_id=alert_id,
                event_type=event_type,
                message=message,
            )
            self.sms_dispatches.append(sms_rec)
            sent.append(sms_rec)
        return sent
