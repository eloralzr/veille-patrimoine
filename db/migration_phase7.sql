-- veille-patrimoine — migration phase 7 (collecte et extraction automatiques)
-- À exécuter une fois dans Supabase > SQL Editor, APRÈS schema.sql. Ré-exécutable.

-- 1. Statut 'erreur' et colonnes de suivi sur documents
alter table documents drop constraint if exists documents_statut_check;
alter table documents add constraint documents_statut_check
  check (statut in ('a_traiter','traite','ignore','erreur'));

alter table documents add column if not exists url_finale  text;
alter table documents add column if not exists erreur      text;
alter table documents add column if not exists nb_fiches   integer;
alter table documents add column if not exists traite_le   timestamptz;
alter table documents add column if not exists fournisseur text;

-- 2. Journal des exécutions de collecte
create table if not exists collecte_runs (
  id            uuid primary key default gen_random_uuid(),
  debut         timestamptz not null default now(),
  fin           timestamptz,
  fournisseur   text,
  modele        text,
  flux_lus      integer default 0,
  docs_vus      integer default 0,
  docs_nouveaux integer default 0,
  docs_extraits integer default 0,
  fiches_creees integer default 0,
  erreurs       integer default 0,
  journal       text
);
alter table collecte_runs enable row level security;

-- 3. Index utile pour la file
create index if not exists documents_cree_idx on documents(cree_le desc);
