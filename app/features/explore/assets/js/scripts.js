// The whole file is inert outside /explore: the asset registry serves it on
// every page, so each entry point checks for the search form first.
function on_explore_page() {
    return document.getElementById('filters') !== null;
}

document.addEventListener('DOMContentLoaded', () => {
    if (!on_explore_page()) return;
    send_query();
});

function send_query() {

    console.log("send query...")

    document.getElementById('results').innerHTML = '';
    document.getElementById("results_not_found").style.display = "none";
    console.log("hide not found icon");

    const filters = document.querySelectorAll('#filters input, #filters select, #filters [type="radio"]');

    // Sequencing guard: each new query supersedes the previous one, so the
    // in-flight request is aborted before a new one starts. Only the latest
    // response can repaint the result list.
    let inFlightController = null;

    filters.forEach(filter => {
        // Selects and radios do not fire "input" on every browser (Chrome only
        // fires "change" for a programmatic option click), so both events run
        // the search. When a control fires both, the abort guard collapses
        // them into a single repaint.
        ['input', 'change'].forEach(eventType => filter.addEventListener(eventType, () => {
            const csrfToken = document.getElementById('csrf_token').value;

            const searchCriteria = {
                csrf_token: csrfToken,
                query: document.querySelector('#query').value,
                publication_type: document.querySelector('#publication_type').value,
                dataset_type: document.querySelector('#dataset_type').value,
                sorting: document.querySelector('[name="sorting"]:checked').value,
            };

            console.log(document.querySelector('#publication_type').value);

            if (inFlightController !== null) {
                inFlightController.abort();
            }
            inFlightController = new AbortController();

            fetch('/explore', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(searchCriteria),
                signal: inFlightController.signal,
            })
                .then(response => response.json())
                .then(data => {

                    console.log(data);
                    document.getElementById('results').innerHTML = '';

                    // results counter
                    const resultCount = data.length;
                    const resultText = resultCount === 1 ? 'dataset' : 'datasets';
                    document.getElementById('results_number').textContent = `${resultCount} ${resultText} found`;

                    if (resultCount === 0) {
                        console.log("show not found icon");
                        document.getElementById("results_not_found").style.display = "block";
                    } else {
                        document.getElementById("results_not_found").style.display = "none";
                    }

                    data.forEach(dataset => {
                        const isSong = dataset.dataset_type === 'song';
                        const domainBadge = isSong
                            ? '<span class="badge sh-badge-song">Song</span>'
                            : '<span class="badge sh-badge-uvl">UVL</span>';
                        let card = document.createElement('div');
                        card.className = 'col-12';
                        card.innerHTML = `
                            <div class="card sh-card-interactive">
                                <div class="card-body">
                                    <div class="d-flex flex-wrap align-items-start justify-content-between gap-2 mb-1">
                                        <h3 class="h4 mb-0"><a href="${dataset.url}" class="sh-card-title-link">${dataset.title}</a></h3>
                                        <div class="d-flex flex-wrap gap-1 align-items-center">
                                            ${domainBadge}
                                            <span class="badge sh-badge-pub" style="cursor: pointer;" onclick="set_publication_type_as_query('${dataset.publication_type}')">${dataset.publication_type}</span>
                                        </div>
                                    </div>
                                    <p class="text-secondary small mb-3">${formatDate(dataset.created_at)}</p>

                                    <div class="row mb-2">
                                        <div class="col-md-3 col-12">
                                            <span class="sh-meta-label">Description</span>
                                        </div>
                                        <div class="col-md-9 col-12">
                                            <p class="card-text mb-0">${dataset.description}</p>
                                        </div>
                                    </div>

                                    <div class="row mb-2">
                                        <div class="col-md-3 col-12">
                                            <span class="sh-meta-label">Authors</span>
                                        </div>
                                        <div class="col-md-9 col-12">
                                            ${dataset.authors.map(author => `
                                                <p class="p-0 m-0 small">${author.name}${author.affiliation ? ` (${author.affiliation})` : ''}${author.orcid ? ` (${author.orcid})` : ''}</p>
                                            `).join('')}
                                        </div>
                                    </div>

                                    ${dataset.tags && dataset.tags.length ? `
                                    <div class="row mb-2">
                                        <div class="col-md-3 col-12">
                                            <span class="sh-meta-label">Tags</span>
                                        </div>
                                        <div class="col-md-9 col-12 d-flex flex-wrap gap-1">
                                            ${dataset.tags.map(tag => `<span class="badge sh-tag-pill" style="cursor: pointer;" onclick="set_tag_as_query('${tag}')">${tag}</span>`).join('')}
                                        </div>
                                    </div>` : ''}

                                    ${dataset.song_metrics ? `
                                    <div class="row mb-3 mt-2 song-summary">
                                        <div class="col-md-3 col-12">
                                            <span class="sh-meta-label">Music summary</span>
                                        </div>
                                        <div class="col-md-9 col-12">
                                            <div class="sh-song-mini-stats d-inline-flex flex-wrap gap-3">
                                                <span>${dataset.song_metrics.number_of_songs} songs</span>
                                                <span>${dataset.song_metrics.number_of_artists} artists</span>
                                                <span>avg. streams ${Number(dataset.song_metrics.average_streams || 0).toFixed(0)}</span>
                                            </div>
                                        </div>
                                    </div>` : ''}

                                    <div class="d-flex flex-wrap gap-2 mt-3 pt-2 border-top">
                                        <a href="${dataset.url}" class="btn btn-outline-primary btn-sm">
                                            <i data-feather="eye" class="center-button-icon"></i>
                                            View dataset
                                        </a>
                                        <a href="/dataset/download/${dataset.id}" class="btn btn-outline-secondary btn-sm">
                                            <i data-feather="download" class="center-button-icon"></i>
                                            Download (${dataset.total_size_in_human_format})
                                        </a>
                                    </div>
                                </div>
                            </div>
                        `;

                        document.getElementById('results').appendChild(card);
                    });

                    if (typeof feather !== 'undefined') {
                        feather.replace();
                    }
                })
                .catch(error => {
                    // Aborted requests are superseded queries, not failures.
                    if (error.name !== 'AbortError') {
                        throw error;
                    }
                });
        }));
    });
}

function formatDate(dateString) {
    const options = {day: 'numeric', month: 'long', year: 'numeric', hour: 'numeric', minute: 'numeric'};
    const date = new Date(dateString);
    return date.toLocaleString('en-US', options);
}

function set_tag_as_query(tagName) {
    const queryInput = document.getElementById('query');
    queryInput.value = tagName.trim();
    queryInput.dispatchEvent(new Event('input', {bubbles: true}));
}

function set_publication_type_as_query(publicationType) {
    const publicationTypeSelect = document.getElementById('publication_type');
    for (let i = 0; i < publicationTypeSelect.options.length; i++) {
        if (publicationTypeSelect.options[i].text === publicationType.trim()) {
            // Set the value of the select to the value of the matching option
            publicationTypeSelect.value = publicationTypeSelect.options[i].value;
            break;
        }
    }
    publicationTypeSelect.dispatchEvent(new Event('input', {bubbles: true}));
}

// Guarded: the asset registry serves every feature's script on every page, so
// this file also loads where the explore form does not exist.
if (document.getElementById('clear-filters')) {
    document.getElementById('clear-filters').addEventListener('click', clearFilters);
}

function clearFilters() {

    // Reset the search query
    let queryInput = document.querySelector('#query');
    queryInput.value = "";

    // Reset the dataset type to its default value
    let datasetTypeSelect = document.querySelector('#dataset_type');
    if (datasetTypeSelect) {
        datasetTypeSelect.value = "any";
    }

    // Reset the publication type to its default value
    let publicationTypeSelect = document.querySelector('#publication_type');
    publicationTypeSelect.value = "any";

    // Reset the sorting option
    let sortingOptions = document.querySelectorAll('[name="sorting"]');
    sortingOptions.forEach(option => {
        option.checked = option.value == "newest";
    });

    // Perform a new search with the reset filters
    queryInput.dispatchEvent(new Event('input', {bubbles: true}));
}

document.addEventListener('DOMContentLoaded', () => {

    if (!on_explore_page()) return;

    let urlParams = new URLSearchParams(window.location.search);
    let queryParam = urlParams.get('query');

    if (queryParam && queryParam.trim() !== '') {

        const queryInput = document.getElementById('query');
        queryInput.value = queryParam
        queryInput.dispatchEvent(new Event('input', {bubbles: true}));
        console.log("throw event");

    } else {
        const queryInput = document.getElementById('query');
        queryInput.dispatchEvent(new Event('input', {bubbles: true}));
    }
});
