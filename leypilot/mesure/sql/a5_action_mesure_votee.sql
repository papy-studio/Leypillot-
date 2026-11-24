-- A5 · Graduer : aucune action sur une mesure qui n'est pas au moins votée.
-- Suppose que la table action (P4) a une colonne mesure_id qui référence mesure(id).
-- Les instructions sont séparées par la ligne « -- @@ » (exécutées une par une).

CREATE OR REPLACE FUNCTION leypilot_a5_verifier_action() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE
    statut_mesure text;
BEGIN
    IF NEW.mesure_id IS NULL THEN
        RETURN NEW;
    END IF;

    SELECT m.statut INTO statut_mesure
    FROM mesure m
    WHERE m.id = NEW.mesure_id
    FOR SHARE;

    IF statut_mesure IS NULL THEN
        RAISE EXCEPTION 'A5 : mesure % introuvable', NEW.mesure_id
            USING ERRCODE = 'foreign_key_violation';
    END IF;

    IF statut_mesure NOT IN ('votee', 'publiee', 'appliquee') THEN
        RAISE EXCEPTION 'A5 : action interdite sur la mesure % au statut %, elle doit être au moins votée',
            NEW.mesure_id, statut_mesure
            USING ERRCODE = 'check_violation';
    END IF;

    RETURN NEW;
END;
$$;
-- @@
DROP TRIGGER IF EXISTS a5_action_mesure_votee ON action;
-- @@
CREATE TRIGGER a5_action_mesure_votee
    BEFORE INSERT OR UPDATE OF mesure_id ON action
    FOR EACH ROW EXECUTE FUNCTION leypilot_a5_verifier_action();
