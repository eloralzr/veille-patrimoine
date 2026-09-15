-- veille-patrimoine — schéma v0 (sans API)
-- À exécuter une seule fois dans Supabase > SQL Editor > New query > Run.
-- Propriétaire : Elora Lazaar — 2026-09-15

create extension if not exists "pgcrypto";

-- 1. Acteurs suivis (candidats, think tanks, organisations, clubs, institutions)
create table if not exists acteurs (
  acteur_id        text primary key,
  nom              text not null,
  type             text not null check (type in ('candidat','think_tank','organisation','club','institution','personnalite_economique')),
  organisation     text,
  camp             text,
  statut           text,
  date_statut      date,
  priorite         text check (priorite in ('P1','P2','P3')),
  frequence_veille text,
  site_officiel    text,
  url_programme    text,
  notes            text,
  actif            boolean not null default true,
  maj_par          text,
  maj_le           date
);

-- 2. Sources de collecte (1 ligne par flux)
create table if not exists sources (
  source_id         text primary key,
  acteur_id         text not null references acteurs(acteur_id),
  type_source       text not null,
  url               text,
  mode_collecte     text,
  frequence         text,
  langue            text default 'fr',
  fiabilite         text,
  robots_ok         text,
  actif             boolean not null default false,
  notes             text,
  derniere_collecte timestamptz
);

-- 3. Documents bruts (alimentés plus tard par la collecte ; file "à traiter")
create table if not exists documents (
  id               uuid primary key default gen_random_uuid(),
  acteur_id        text references acteurs(acteur_id),
  source_id        text references sources(source_id),
  source_type      text,
  url              text,
  titre            text,
  date_publication date,
  texte            text,
  hash             text unique,
  statut           text not null default 'a_traiter' check (statut in ('a_traiter','traite','ignore')),
  cree_le          timestamptz not null default now()
);

-- 4. Fiches "mesure" (cœur de l'outil)
create table if not exists mesures (
  id             uuid primary key default gen_random_uuid(),
  acteur_id      text not null references acteurs(acteur_id),
  document_id    uuid references documents(id),
  theme_id       text not null,
  sous_theme_id  text not null,
  mots_cles      text[],
  titre          text not null,
  resume         text not null,
  citation       text,
  nature         text not null check (nature in ('engagement','piste','proposition','reaction','chiffrage')),
  impact_client  text,
  url_source     text not null,
  date_source    date,
  confiance      text not null check (confiance in ('eleve','moyen','incertain')),
  statut         text not null default 'brut' check (statut in ('brut','verifie','publie','retire')),
  saisi_par      text,
  valide_par     text,
  json_brut      jsonb,
  cree_le        timestamptz not null default now(),
  maj_le         timestamptz not null default now()
);

create index if not exists mesures_acteur_idx on mesures(acteur_id);
create index if not exists mesures_theme_idx  on mesures(theme_id, sous_theme_id);
create index if not exists mesures_statut_idx on mesures(statut);
create index if not exists documents_statut_idx on documents(statut);

-- Mise à jour automatique de maj_le
create or replace function set_maj_le() returns trigger language plpgsql as $$
begin new.maj_le = now(); return new; end $$;
drop trigger if exists mesures_maj_le on mesures;
create trigger mesures_maj_le before update on mesures for each row execute function set_maj_le();

-- Sécurité : l'application utilise la clé service_role côté serveur (Streamlit Cloud).
-- On active RLS pour que la clé publique "anon" ne puisse rien lire.
alter table acteurs   enable row level security;
alter table sources   enable row level security;
alter table documents enable row level security;
alter table mesures   enable row level security;
