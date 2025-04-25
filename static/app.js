document.addEventListener('DOMContentLoaded', () => {
    const activityForm = document.getElementById('activity-form');
    const activityList = document.getElementById('activity-list');
    const activityIdInput = document.getElementById('activity-id');
    const activityNameInput = document.getElementById('activity-name');
    const activityMinutesInput = document.getElementById('activity-minutes');
    const activityCategoryInput = document.getElementById('activity-category');
    const cancelEditButton = document.getElementById('cancel-edit');
    const generatedLinkInput = document.getElementById('generated-calendar-link');
    const copyLinkButton = document.getElementById('copy-link-button');

    const apiUrl = '/api/activities';

    // ---- Fonctions ----

    // Charger les activités depuis l'API
    async function loadActivities() {
        try {
            const response = await fetch(apiUrl);
            if (!response.ok) {
                throw new Error(`Erreur HTTP: ${response.status}`);
            }
            const activities = await response.json();
            displayActivities(activities);
        } catch (error) {
            console.error("Erreur lors du chargement des activités:", error);
            activityList.innerHTML = '<li>Erreur chargement activités.</li>';
        }
    }

    // Afficher les activités dans la liste UL
    function displayActivities(activities) {
        activityList.innerHTML = ''; // Vider la liste actuelle
        if (activities.length === 0) {
            activityList.innerHTML = '<li>Aucune activité définie.</li>';
            return;
        }
        activities.forEach(activity => {
            const li = document.createElement('li');
            li.innerHTML = `
                <span>
                    <strong>${activity.name}</strong>
                    (${activity.weekly_minutes} min/semaine) -
                    <em>${activity.category}</em>
                </span>
                <span class="actions">
                    <button class="edit-btn" data-id="${activity.id}">Modifier</button>
                    <button class="delete-btn" data-id="${activity.id}">Supprimer</button>
                </span>
            `;
            activityList.appendChild(li);
        });
    }

    // Gérer la soumission du formulaire (Ajout/Modification)
    async function handleActivitySubmit(event) {
        event.preventDefault(); // Empêche le rechargement de la page

        const activityData = {
            name: activityNameInput.value,
            weekly_minutes: parseInt(activityMinutesInput.value, 10),
            category: activityCategoryInput.value,
        };

        const id = activityIdInput.value;
        const method = id ? 'PUT' : 'POST';
        const url = id ? `${apiUrl}/${id}` : apiUrl;

        try {
            const response = await fetch(url, {
                method: method,
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(activityData),
            });

            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `Erreur ${response.status}`);
            }

            resetForm();
            loadActivities(); // Recharger la liste

        } catch (error) {
            console.error(`Erreur lors de ${id ? 'modification' : 'ajout'} activité:`, error);
            alert(`Erreur: ${error.message}`);
        }
    }

    // Gérer la suppression d'une activité
    async function handleDeleteActivity(event) {
        if (!event.target.classList.contains('delete-btn')) return;

        const id = event.target.dataset.id;
        if (!confirm('Voulez-vous vraiment supprimer cette activité ?')) return;

        try {
            const response = await fetch(`${apiUrl}/${id}`, { method: 'DELETE' });
            if (!response.ok) {
                const errorData = await response.json();
                throw new Error(errorData.message || `Erreur ${response.status}`);
            }
            loadActivities(); // Recharger la liste
        } catch (error) {
             console.error("Erreur lors de la suppression:", error);
             alert(`Erreur: ${error.message}`);
        }
    }

     // Pré-remplir le formulaire pour modification
    function handleEditActivity(event) {
        if (!event.target.classList.contains('edit-btn')) return;

        const id = event.target.dataset.id;
        const activityItem = event.target.closest('li');
        const name = activityItem.querySelector('strong').textContent;
        const minutes = activityItem.querySelector('span').textContent.match(/\((\d+) min/)[1];
        const category = activityItem.querySelector('em').textContent;

        activityIdInput.value = id;
        activityNameInput.value = name;
        activityMinutesInput.value = minutes;
        activityCategoryInput.value = category;
        cancelEditButton.style.display = 'inline-block'; // Afficher Annuler
         activityForm.querySelector('button[type="submit"]').textContent = 'Modifier';
         activityForm.scrollIntoView({ behavior: 'smooth' }); // Scroller vers le formulaire
    }

    // Réinitialiser le formulaire
    function resetForm() {
        activityForm.reset();
        activityIdInput.value = '';
        cancelEditButton.style.display = 'none';
        activityForm.querySelector('button[type="submit"]').textContent = 'Ajouter/Modifier';
    }

    // Copier le lien du calendrier généré
    function copyGeneratedLink() {
         generatedLinkInput.select();
         try {
             document.execCommand('copy');
             // Peut-être afficher un petit message de succès
             console.log('Lien copié !');
         } catch (err) {
             console.error('Erreur lors de la copie du lien:', err);
             alert('Impossible de copier le lien automatiquement.');
         }
    }


    // ---- Écouteurs d'événements ----
    activityForm.addEventListener('submit', handleActivitySubmit);
    activityList.addEventListener('click', handleDeleteActivity); // Utilise la délégation d'événement
    activityList.addEventListener('click', handleEditActivity);
    cancelEditButton.addEventListener('click', resetForm);
    copyLinkButton.addEventListener('click', copyGeneratedLink);


    // ---- Initialisation ----
    loadActivities(); // Charger les activités au démarrage
     // Afficher l'URL complète du calendrier généré
    generatedLinkInput.value = `${window.location.origin}/calendar/feed.ics`;

});