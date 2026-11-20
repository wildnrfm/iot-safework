"""Jalankan: python -m safework --fake   (simulasi)   atau   python -m safework --weights best.pt --serial COM5"""
from __future__ import annotations

import logging

from .app import create_app
from .bootstrap import build_service
from .config import Settings


def main(argv=None) -> None:
    import uvicorn

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = Settings.from_args(argv)
    service = build_service(settings)
    app = create_app(service)

    class GracefulServer(uvicorn.Server):
        """Saat Ctrl+C, akhiri stream video lebih dulu. Tanpa ini uvicorn menunggu koneksi MJPEG yang
        masih terbuka sampai batas waktu, lalu mencetak galat CancelledError."""

        def handle_exit(self, sig, frame):
            try:
                service.request_stop()
            except Exception:  # noqa: BLE001 - jangan menghalangi shutdown
                logging.getLogger(__name__).exception("request_stop gagal")
            super().handle_exit(sig, frame)

    config = uvicorn.Config(app, host=settings.host, port=settings.port, log_level="info",
                            access_log=settings.access_log, timeout_graceful_shutdown=3)
    mode = "simulasi" if settings.fake else "nyata"
    print(f"SAFEWORK AI ({mode}) -> http://{settings.host}:{settings.port}   (Ctrl+C untuk berhenti)")
    try:
        GracefulServer(config).run()
    except KeyboardInterrupt:
        pass  # uvicorn.run() juga menelannya; shutdown sudah selesai bersih sebelum sampai di sini


if __name__ == "__main__":
    main()
