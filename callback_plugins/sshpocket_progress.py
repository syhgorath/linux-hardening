# SSHPOCKET_PROGRESS satırları (docs/ilerleme-satirlari.md). Bildirim tipi: mevcut çıktıya ek satır yazar, stdout callback'ini DEĞİŞTİRMEZ.
# Eklenti hatası sertleştirmeyi asla durdurmaz: herhangi bir istisna eklentiyi sessizce kapatır.
from __future__ import annotations

import functools
import json
import os

from ansible import context
from ansible.plugins.callback import CallbackBase

DOCUMENTATION = """
    name: sshpocket_progress
    type: notification
    short_description: alan başına SSHPOCKET_PROGRESS satırı yazar
    description:
      - Her alan (rol) için başladı/bitti satırı ve bitişte değişen/atlanan sayısı.
"""

PREFIX = "hardening_"
# Tahmini süreler (saniye): yalnız gerçekten uzun süren görevler. Bekleme başladığında (ilk async poll) bir kez bildirilir.
WAIT_ESTIMATE = {"aide": 300}


def _safe(fn):
    @functools.wraps(fn)
    def wrapper(self, *args, **kwargs):
        if self._off:
            return None
        try:
            return fn(self, *args, **kwargs)
        except Exception:  # noqa: BLE001 - ilerleme göstergesi sertleştirmeyi yarım bırakmamalı
            self._off = True
            return None
    return wrapper


class CallbackModule(CallbackBase):
    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = "notification"
    CALLBACK_NAME = "sshpocket_progress"
    CALLBACK_NEEDS_ENABLED = True

    def __init__(self):
        super().__init__()
        self._off = False
        self._plan = []
        self._cur = None
        self._stat = {}
        self._waited = set()
        try:
            self._check = bool(context.CLIARGS.get("check"))
        except Exception:  # noqa: BLE001
            self._check = False

    def _emit(self, line):
        self._display.display(line)

    @staticmethod
    def _alan(task):
        role = getattr(task, "_role", None)
        name = role.get_name() if role is not None else ""
        name = name.split(".")[-1]
        return name[len(PREFIX):] if name.startswith(PREFIX) else None

    def _line(self, alan, durum, extra=""):
        return f"SSHPOCKET_PROGRESS alan={alan} sira={self._plan.index(alan) + 1}/{len(self._plan)} durum={durum}{extra}"

    @_safe
    def _close(self, ok=True):
        alan = self._cur
        self._cur = None
        if alan is None or not ok:
            return
        s = self._stat.get(alan, {"degisen": 0, "atlanan": 0, "kesin_degil": 0, "uyari": 0})
        extra = f" degisen={s['degisen']} atlanan={s['atlanan']} kesin={0 if s['kesin_degil'] else 1}"
        if s["uyari"] > 0:
            extra += f" uyari={s['uyari']}"
        self._emit(self._line(alan, "bitti", extra))

    @_safe
    def v2_playbook_on_task_start(self, task, is_conditional):
        alan = self._alan(task)
        if alan == self._cur:
            return
        self._close()
        if alan is not None and alan in self._plan:
            self._cur = alan
            self._stat[alan] = {"degisen": 0, "atlanan": 0, "kesin_degil": 0, "uyari": 0}
            self._emit(self._line(alan, "basladi"))

    @_safe
    def v2_runner_on_ok(self, result):
        facts = result._result.get("ansible_facts") or {}
        plan = facts.get("hardening_progress_areas")
        if plan is not None and not self._plan:
            plan = json.loads(plan) if isinstance(plan, str) else list(plan)
            if all(isinstance(p, str) and p.isascii() and p.replace("_", "").isalnum() for p in plan):
                self._plan = plan
            return
        s = self._stat.get(self._alan(result._task))
        if s is None:
            return
        if result.is_changed():
            s["degisen"] += 1
        msg = result._result.get("msg")
        if isinstance(msg, str) and msg.startswith("UYARI"):
            s["uyari"] += 1

    @_safe
    def v2_runner_on_skipped(self, result):
        s = self._stat.get(self._alan(result._task))
        if s is None:
            return
        s["atlanan"] += 1
        reason = f"{result._result.get('skip_reason', '')} {result._result.get('msg', '')}".lower()
        if self._check and "check mode" in reason:
            s["kesin_degil"] += 1

    @_safe
    def v2_runner_on_failed(self, result, ignore_errors=False):
        if not ignore_errors:
            self._close(ok=False)

    @_safe
    def v2_runner_on_unreachable(self, result):
        self._close(ok=False)

    @_safe
    def v2_runner_on_async_poll(self, result):
        # Poll olayinin gorevi Ansible'in kendi async_status gorevidir (rol bilgisi yok); calisma sirali oldugundan acik alan odur.
        alan = self._cur
        key = (alan, result._result.get("ansible_job_id"))
        if alan in WAIT_ESTIMATE and key not in self._waited:
            self._waited.add(key)
            self._emit(self._line(alan, "basladi", f" bekle_tahmin={WAIT_ESTIMATE[alan]}"))

    @_safe
    def v2_playbook_on_stats(self, stats):
        self._close()
