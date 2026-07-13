const places = [
    {
        id: 'gyeongbokgung',
        name: '경복궁',
        category: '역사 명소',
        lat: 37.579617,
        lng: 126.977041,
        rating: 4.6,
        reviews: '리뷰 98,000+',
        address: '서울특별시 종로구 사직로 161',
        hours: '09:00-18:00, 화요일 휴무',
        tip: '광화문에서 시작해 국립고궁박물관까지 함께 둘러보기 좋습니다.',
        description: '조선 왕조의 중심 궁궐로, 넓은 전각과 북악산 풍경이 이어지는 서울 대표 역사 공간입니다.',
        image: 'https://images.unsplash.com/photo-1578922746465-3a80a228f223?auto=format&fit=crop&w=900&q=80',
    },
    {
        id: 'n-seoul-tower',
        name: 'N서울타워',
        category: '전망대',
        lat: 37.551169,
        lng: 126.988227,
        rating: 4.4,
        reviews: '리뷰 62,000+',
        address: '서울특별시 용산구 남산공원길 105',
        hours: '10:30-22:30',
        tip: '해질녘에 올라가면 도심 야경까지 자연스럽게 이어집니다.',
        description: '남산 정상에 있는 서울의 대표 전망 명소로, 한강과 도심 스카이라인을 한눈에 볼 수 있습니다.',
        image: 'https://images.unsplash.com/photo-1548115184-bc6544d06a58?auto=format&fit=crop&w=900&q=80',
    },
    {
        id: 'ddp',
        name: '동대문디자인플라자',
        category: '문화 공간',
        lat: 37.566525,
        lng: 127.009224,
        rating: 4.3,
        reviews: '리뷰 47,000+',
        address: '서울특별시 중구 을지로 281',
        hours: '10:00-20:00',
        tip: '전시 일정과 야간 외관 조명을 함께 확인하면 좋습니다.',
        description: '곡선형 건축물과 전시, 디자인 마켓이 모인 동대문 중심의 복합 문화 공간입니다.',
        image: 'https://images.unsplash.com/photo-1538485399081-7c8edc53c7e7?auto=format&fit=crop&w=900&q=80',
    },
    {
        id: 'seoul-forest',
        name: '서울숲',
        category: '도시 공원',
        lat: 37.544388,
        lng: 127.037442,
        rating: 4.6,
        reviews: '리뷰 31,000+',
        address: '서울특별시 성동구 뚝섬로 273',
        hours: '상시 개방',
        tip: '성수동 카페 거리와 묶어 걷기 좋은 코스입니다.',
        description: '숲길, 잔디마당, 생태 공간이 이어지는 넓은 도심 공원입니다.',
        image: 'https://images.unsplash.com/photo-1500530855697-b586d89ba3ee?auto=format&fit=crop&w=900&q=80',
    },
    {
        id: 'coex',
        name: '스타필드 코엑스몰',
        category: '쇼핑몰',
        lat: 37.511805,
        lng: 127.059159,
        rating: 4.4,
        reviews: '리뷰 54,000+',
        address: '서울특별시 강남구 영동대로 513',
        hours: '10:30-22:00',
        tip: '별마당도서관과 봉은사를 함께 방문하기 편합니다.',
        description: '강남 삼성동에 있는 대형 복합 쇼핑 공간으로, 쇼핑과 식당, 전시 시설이 밀집해 있습니다.',
        image: 'https://images.unsplash.com/photo-1519567241046-7f570eee3ce6?auto=format&fit=crop&w=900&q=80',
    },
    {
        id: 'lotte-world-tower',
        name: '롯데월드타워',
        category: '랜드마크',
        lat: 37.51255,
        lng: 127.102535,
        rating: 4.5,
        reviews: '리뷰 73,000+',
        address: '서울특별시 송파구 올림픽로 300',
        hours: '10:30-22:00',
        tip: '석촌호수 산책과 서울스카이 전망대를 함께 즐기기 좋습니다.',
        description: '잠실에 위치한 초고층 랜드마크로, 쇼핑몰과 전망대, 식음 공간이 연결되어 있습니다.',
        image: 'https://images.unsplash.com/photo-1580655653885-65763b2597d0?auto=format&fit=crop&w=900&q=80',
    },
];

const map = L.map('map', {
    zoomControl: false,
    minZoom: 11,
}).setView([37.5665, 126.9780], 12);

L.control.zoom({ position: 'bottomright' }).addTo(map);

L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
    maxZoom: 19,
    attribution: '&copy; OpenStreetMap contributors',
}).addTo(map);

const markerById = new Map();
const bounds = L.latLngBounds(places.map((place) => [place.lat, place.lng]));

places.forEach((place, index) => {
    const icon = L.divIcon({
        className: '',
        html: `<div class="place-marker"><span>${index + 1}</span></div>`,
        iconSize: [34, 34],
        iconAnchor: [17, 31],
    });

    const marker = L.marker([place.lat, place.lng], { icon })
        .addTo(map)
        .on('click', () => selectPlace(place.id));

    markerById.set(place.id, marker);
});

map.fitBounds(bounds.pad(0.16));

const panel = document.querySelector('#placePanel');
const closePanel = document.querySelector('#closePanel');
const searchInput = document.querySelector('#placeSearch');
const clearSearch = document.querySelector('#clearSearch');
const resultsPanel = document.querySelector('#resultsPanel');

function selectPlace(placeId) {
    const place = places.find((item) => item.id === placeId);
    if (!place) {
        return;
    }

    document.querySelector('#placePhoto').style.backgroundImage = `url("${place.image}")`;
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
    map.flyTo([place.lat, place.lng], 15, { duration: 0.7 });
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

closePanel.addEventListener('click', closePlacePanel);

clearSearch.addEventListener('click', () => {
    searchInput.value = '';
    renderResults();
    searchInput.focus();
    map.fitBounds(bounds.pad(0.16));
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
