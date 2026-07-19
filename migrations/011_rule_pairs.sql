-- N7 (Fase 10): notification rules gain an optional pair scope.
-- '["*"]' = all pairs. Retrocompatible: existing rules default to '*', so they
-- keep firing for every pair (aceite: regras antigas seguem valendo).
ALTER TABLE notification_rules ADD COLUMN pairs TEXT NOT NULL DEFAULT '["*"]';
