let map;
let placesService;
let selectedMarker;
let searchDebounce;
let activeProvider = null;

const panel = document.querySelector('#placePanel');
const closePanel = document.querySelector('#closePanel');
const searchInput = document.querySelector('#placeSearch');
const clearSearch = document.querySelector('#clearSearch');
const resultsPanel = document.querySelector('#resultsPanel');
const mapNotice = document.querySelector('#mapNotice');

window.initGoogleMap = function initGoogleMap() {
    activeProvider = 'google';

    map = new google.maps.Map(document.querySelector('#map'), {
        center: { lat: 37.5665, lng: 126.9780 },
        zoom: 13,
        mapTypeControl: false,
        fullscreenControl: false,
        streetViewControl: true,
        clickableIcons: true,
        gestureHandling: 'greedy',
    });

    placesService = new google.maps.places.PlacesService(map);
    selectedMarker = new google.maps.Marker({ map });

    map.addListener('click', (event) => {
        if (!event.placeId) {
            return;
        }

        event.stop();
        showGooglePlaceDetails(event.placeId, event.latLng);
    });

    bindUiEvents();
    showNotice('지도 위 장소 아이콘을 클릭하거나 검색해서 Google Maps 장소 정보를 볼 수 있습니다.');
};

document.addEventListener('DOMContentLoaded', () => {
    if (window.GOOGLE_MAPS_ENABLED) {
        return;
    }

    activeProvider = 'leaflet';
    bindUiEvents();
    initLeafletMap();
});

function initLeafletMap() {
    if (!window.L) {
        showNotice('지도 라이브러리를 불러오지 못했습니다. 네트워크 상태를 확인해주세요.');
        return;
    }

    map = L.map('map', {
        zoomControl: false,
        minZoom: 11,
    }).setView([37.5665, 126.9780], 13);

    L.control.zoom({ position: 'bottomright' }).addTo(map);
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        attribution: '&copy; OpenStreetMap contributors',
    }).addTo(map);

    showNotice('GOOGLE_MAPS_API_KEY가 없어 Google Maps 장소 클릭/검색은 비활성화되어 있습니다.');
}

function searchGooglePlaces(query) {
    const normalizedQuery = query.trim();

    if (activeProvider !== 'google' || !normalizedQuery) {
        resultsPanel.classList.remove('is-open');
        resultsPanel.innerHTML = '';
        return;
    }

    if (normalizedQuery.length < 2) {
        renderMessage('두 글자 이상 입력하세요.');
        return;
    }

    placesService.textSearch(
        {
            query: normalizedQuery,
            bounds: map.getBounds(),
            region: 'kr',
        },
        (results, status) => {
            if (status !== google.maps.places.PlacesServiceStatus.OK || !results?.length) {
                renderMessage('검색 결과가 없습니다.');
                return;
            }

            renderResults(results.slice(0, 10));
        },
    );
}

function showGooglePlaceDetails(placeId, position = null) {
    placesService.getDetails(
        {
            placeId,
            fields: [
                'business_status',
                'formatted_address',
                'formatted_phone_number',
                'geometry',
                'name',
                'opening_hours',
                'place_id',
                'rating',
                'types',
                'url',
                'user_ratings_total',
                'website',
            ],
        },
        (place, status) => {
            if (status !== google.maps.places.PlacesServiceStatus.OK || !place) {
                showNotice('장소 상세 정보를 불러오지 못했습니다.');
                return;
            }

            renderPlaceDetails(normalizeGooglePlace(place));
            const placePosition = position || place.geometry?.location;

            if (placePosition) {
                selectedMarker.setPosition(placePosition);
                selectedMarker.setTitle(place.name || '');
                selectedMarker.setVisible(true);
                map.panTo(placePosition);
                map.setZoom(Math.max(map.getZoom(), 16));
            }
        },
    );
}

function normalizeGooglePlace(place) {
    const rating = typeof place.rating === 'number' ? place.rating : null;
    const reviewText = place.user_ratings_total
        ? `리뷰 ${place.user_ratings_total.toLocaleString()}개`
        : '리뷰 정보 없음';
    const primaryType = formatPlaceType(place.types?.[0]);
    const openNow = place.opening_hours?.isOpen?.();
    const hours = place.opening_hours?.weekday_text?.join(' / ')
        || (typeof openNow === 'boolean' ? (openNow ? '영업 중' : '영업 종료') : '운영 정보 없음');
    const contact = [
        place.formatted_phone_number,
        place.website ? `<a href="${place.website}" target="_blank" rel="noreferrer">웹사이트</a>` : '',
        place.url ? `<a href="${place.url}" target="_blank" rel="noreferrer">Google Maps</a>` : '',
    ].filter(Boolean).join(' · ') || '연락처 정보 없음';

    return {
        name: place.name || '이름 없는 장소',
        category: primaryType,
        rating,
        reviewText,
        address: place.formatted_address || '주소 정보 없음',
        description: place.business_status ? `상태: ${formatBusinessStatus(place.business_status)}` : 'Google Maps 장소 정보입니다.',
        hours,
        contact,
    };
}

function renderPlaceDetails(place) {
    document.querySelector('#placeCategory').textContent = place.category;
    document.querySelector('#placeName').textContent = place.name;
    document.querySelector('#placeRating').textContent = place.rating ? place.rating.toFixed(1) : '-';
    document.querySelector('#placeStars').textContent = place.rating ? buildStars(place.rating) : '';
    document.querySelector('#placeReviews').textContent = place.reviewText;
    document.querySelector('#placeAddress').textContent = place.address;
    document.querySelector('#placeDescription').textContent = place.description;
    document.querySelector('#placeHours').textContent = place.hours;
    document.querySelector('#placeTip').innerHTML = place.contact;

    panel.classList.add('is-open');
    panel.setAttribute('aria-hidden', 'false');
}

function renderResults(results) {
    resultsPanel.innerHTML = results.map((place) => (
        `<button class="result-button" type="button" data-place-id="${place.place_id}">
            <strong>${escapeHtml(place.name || '이름 없는 장소')}</strong>
            <span>${escapeHtml(place.formatted_address || place.vicinity || '')}</span>
        </button>`
    )).join('');

    resultsPanel.classList.add('is-open');
}

function renderMessage(message) {
    resultsPanel.innerHTML = `<p class="result-message">${escapeHtml(message)}</p>`;
    resultsPanel.classList.add('is-open');
}

function buildStars(rating) {
    const rounded = Math.round(rating);
    return '★★★★★'.slice(0, rounded) + '☆☆☆☆☆'.slice(0, 5 - rounded);
}

function formatPlaceType(type) {
    if (!type) {
        return '장소';
    }

    const labels = {
        accounting: '회계',
        airport: '공항',
        amusement_park: '놀이공원',
        aquarium: '수족관',
        art_gallery: '미술관',
        bakery: '베이커리',
        bank: '은행',
        bar: '바',
        book_store: '서점',
        cafe: '카페',
        church: '교회',
        city_hall: '시청',
        clothing_store: '의류 매장',
        convenience_store: '편의점',
        department_store: '백화점',
        drugstore: '약국',
        electronics_store: '전자제품 매장',
        embassy: '대사관',
        florist: '꽃집',
        food: '음식점',
        gym: '헬스장',
        hair_care: '미용실',
        hospital: '병원',
        library: '도서관',
        lodging: '숙박',
        meal_takeaway: '테이크아웃',
        movie_theater: '영화관',
        museum: '박물관',
        park: '공원',
        parking: '주차장',
        pharmacy: '약국',
        restaurant: '음식점',
        school: '학교',
        shopping_mall: '쇼핑몰',
        stadium: '경기장',
        store: '상점',
        subway_station: '지하철역',
        tourist_attraction: '관광 명소',
        train_station: '기차역',
        transit_station: '대중교통',
        university: '대학교',
        zoo: '동물원',
    };

    return labels[type] || type.replaceAll('_', ' ');
}

function formatBusinessStatus(status) {
    const labels = {
        OPERATIONAL: '운영 중',
        CLOSED_TEMPORARILY: '임시 휴업',
        CLOSED_PERMANENTLY: '폐업',
    };

    return labels[status] || status;
}

function escapeHtml(value) {
    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#039;');
}

function closePlacePanel() {
    panel.classList.remove('is-open');
    panel.setAttribute('aria-hidden', 'true');
}

function showNotice(message) {
    mapNotice.textContent = message;
    mapNotice.hidden = false;
}

function bindUiEvents() {
    closePanel.addEventListener('click', closePlacePanel);

    clearSearch.addEventListener('click', () => {
        searchInput.value = '';
        resultsPanel.innerHTML = '';
        resultsPanel.classList.remove('is-open');
        searchInput.focus();
    });

    searchInput.addEventListener('input', (event) => {
        window.clearTimeout(searchDebounce);
        searchDebounce = window.setTimeout(() => {
            searchGooglePlaces(event.target.value);
        }, 240);
    });

    searchInput.addEventListener('focus', () => {
        if (searchInput.value.trim()) {
            searchGooglePlaces(searchInput.value);
        }
    });

    searchInput.addEventListener('keydown', (event) => {
        if (event.key === 'Enter') {
            event.preventDefault();
            window.clearTimeout(searchDebounce);
            searchGooglePlaces(searchInput.value);
        }
    });

    resultsPanel.addEventListener('click', (event) => {
        const button = event.target.closest('[data-place-id]');
        if (!button) {
            return;
        }

        showGooglePlaceDetails(button.dataset.placeId);
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
