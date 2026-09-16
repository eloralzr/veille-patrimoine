-- Remettre en file les documents ignorés pour "texte trop court" (à rejouer après la correction Google Actualités)
update documents
set statut = 'a_traiter', erreur = null, traite_le = null
where statut = 'ignore' and erreur like 'texte trop court%';
