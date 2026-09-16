-- Remettre en file les documents en erreur (à rejouer après correction de la clé Gemini)
update documents
set statut = 'a_traiter', erreur = null, traite_le = null
where statut = 'erreur';
