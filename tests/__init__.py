import logging

# Beberapa tes sengaja memicu kegagalan (indikator rusak, port serial belum ada, kamera dicabut).
# Log peringatannya dimatikan agar keluaran tes tidak tampak seperti galat.
logging.disable(logging.CRITICAL)
