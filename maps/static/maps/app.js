let map;
let places = [];
let activeProvider = null;

const markersById = new Map();
const panel = document.querySelector('#placePanel');
const closePanel = document.querySelector('#closePanel');
const searchInput = document.querySelector('#placeSearch');
const clearSearch = document.querySelector('#clearSearch');
const resultsPanel = document.querySelector('#resultsPanel');
const mapNotice = document.querySelector('#mapNotice');

window.initGoogleMap = async function initGoogleMap() {
    activeProvider = 'google';
    places = await loadPlaces();

    const center = { lat: 37.5665, lng: 126.9780 };
    map = new google.maps.Map(document.querySelector('#map'), {
        center,
        zoom: 12,
        mapTypeControl: false,
        fullscreenControl: false,
        streetViewControl: true,
        clickableIcons: true,
        gestureHandling: 'greedy',
    });

    const bounds = new google.maps.LatLngBounds();

    places.forEach((place) => {
        const position = { lat: place.lat, lng: place.lng };
        const marker = new google.maps.Marker({
            position,
            map,
            title: place.name,
            label: {
                text: place.name.slice(0, 1),
                color: '#ffffff',
                fontWeight: '700',
            },
        });

        marker.addListener('click', () => selectPlace(place.id));
        markersById.set(place.id, marker);
        bounds.extend(position);
    });

    map.fitBounds(bounds, 64);
    renderResults();
};

document.addEventListener('DOMContentLoaded', async () => {
    bindUiEvents();

    if (window.GOOGLE_MAPS_ENABLED) {
        return;
    }

    activeProvider = 'leaflet';
    places = await loadPlaces();
    initLeafletMap();
    renderResults();
});

async function loadPlaces() {
    const response = await fetch('/api/places/');
    if (!response.ok) {
        showNotice('장소 데이터를 불러오지 못했습니다.');
        return [];
    }

    const data = await response.json();
    return data.places;
}

function initLeafletMap() {
    if (!window.L) {
        showNotice('지도 라이브러리를 불러오지 못했습니다. 네트워크 상태를 확인해주세요.');
        return;
    }

    map = L.map('map', {
        zoomControl: false,
        minZoom: 11,
    }).setView([37.5665, 126.9780], 12);

    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);

    const bounds = L.latLngBounds(places.map((place) => [place.lat, place.lng]));

    places.forEach((place) => {
        const marker = L.marker([place.lat, place.lng])
            .addTo(map)
            .bindTooltip(place.name, { direction: 'top', offset: [0, -8] })
            .on('click', () => selectPlace(place.id));

        markersById.set(place.id, marker);
    });

    map.fitBounds(bounds.pad(0.16));
    showNotice('GOOGLE_MAPS_API_KEY가 없어 OpenStreetMap 개발용 지도로 표시 중입니다.');
}

function selectPlace(placeId) {
    const place = places.find((item) => item.id === placeId);
    if (!place) {
        return;
    }

    document.querySelector('#placeCategory').textContent = place.category;
    document.querySelector('#placeName').textContent = place.name;
    document.querySelector('#placeRating').textContent = place.rating.toFixed(1);
    document.querySelector('#placeStars').textContent = buildStars(place.rating);
    document.querySelector('#placeReviews').textContent = place.reviews;
    document.querySelector('#placeAddress').textContent = place.address;
    document.querySelector('#placeDescription').textContent = place.description;
    document.querySelector('#placeHours').textContent = place.hours;
    document.querySelector('#placeTip').textContent = place.tip;

    panel.classList.add('is-open');
    panel.setAttribute('aria-hidden', 'false');

    if (activeProvider === 'google') {
        map.panTo({ lat: place.lat, lng: place.lng });
        map.setZoom(15);
        return;
    }

    if (activeProvider === 'leaflet') {
        map.flyTo([place.lat, place.lng], 15, { duration: 0.7 });
    }
}

function buildStars(rating) {
    const rounded = Math.round(rating);
    return '★★★★★'.slice(0, rounded) + '☆☆☆☆☆'.slice(0, 5 - rounded);
}

function closePlacePanel() {
    panel.classList.remove('is-open');
    panel.setAttribute('aria-hidden', 'true');
}

function renderResults(query = '') {
    const normalizedQuery = query.trim().toLowerCase();
    const filteredPlaces = normalizedQuery
        ? places.filter((place) => {
            const text = `${place.name} ${place.category} ${place.address}`.toLowerCase();
            return text.includes(normalizedQuery);
        })
        : places;

    resultsPanel.innerHTML = filteredPlaces.map((place) => (
        `<button class="result-button" type="button" data-place-id="${place.id}">
            <strong>${place.name}</strong>
            <span>${place.category}</span>
        </button>`
    )).join('');

    resultsPanel.classList.toggle('is-open', document.activeElement === searchInput);
}

function resetMapView() {
    if (!places.length || !map) {
        return;
    }

    if (activeProvider === 'google') {
        const bounds = new google.maps.LatLngBounds();
        places.forEach((place) => bounds.extend({ lat: place.lat, lng: place.lng }));
        map.fitBounds(bounds, 64);
        return;
    }

    const bounds = L.latLngBounds(places.map((place) => [place.lat, place.lng]));
    map.fitBounds(bounds.pad(0.16));
}

function showNotice(message) {
    mapNotice.textContent = message;
    mapNotice.hidden = false;
}

function bindUiEvents() {
    closePanel.addEventListener('click', closePlacePanel);

    clearSearch.addEventListener('click', () => {
        searchInput.value = '';
        renderResults();
        searchInput.focus();
        resetMapView();
    });

    searchInput.addEventListener('input', (event) => {
        renderResults(event.target.value);
    });

    searchInput.addEventListener('focus', () => {
        renderResults(searchInput.value);
    });

    resultsPanel.addEventListener('click', (event) => {
        const button = event.target.closest('[data-place-id]');
        if (!button) {
            return;
        }

        selectPlace(button.dataset.placeId);
        resultsPanel.classList.remove('is-open');
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') {
            closePlacePanel();
            resultsPanel.classList.remove('is-open');
            searchInput.blur();
        }
    });

    document.addEventListener('click', (event) => {
        const clickedSearchArea = event.target.closest('.topbar') || event.target.closest('#resultsPanel');
        if (!clickedSearchArea) {
            resultsPanel.classList.remove('is-open');
        }
    });
}
