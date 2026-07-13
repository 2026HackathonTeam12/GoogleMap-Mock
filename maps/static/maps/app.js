let map;
let placesService;
let selectedMarker;
let searchDebounce;
let activeProvider = null;
let selectedPlace = null;

const panel = document.querySelector('#placePanel');
const closePanel = document.querySelector('#closePanel');
const searchInput = document.querySelector('#placeSearch');
const clearSearch = document.querySelector('#clearSearch');
const resultsPanel = document.querySelector('#resultsPanel');
const mapNotice = document.querySelector('#mapNotice');
const reviewForm = document.querySelector('#reviewForm');
const reviewAuthor = document.querySelector('#reviewAuthor');
const reviewRating = document.querySelector('#reviewRating');
const reviewContent = document.querySelector('#reviewContent');
const reviewDeletePassword = document.querySelector('#reviewDeletePassword');
const reviewMessage = document.querySelector('#reviewMessage');
const reviewList = document.querySelector('#reviewList');
const deleteReviewDialog = document.querySelector('#deleteReviewDialog');
const deleteReviewForm = document.querySelector('#deleteReviewForm');
const deleteReviewPassword = document.querySelector('#deleteReviewPassword');
const cancelDeleteReview = document.querySelector('#cancelDeleteReview');
let pendingDeleteReviewId = null;

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
                'types',
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
    const primaryType = formatPlaceType(place.types?.[0]);
    const openNow = place.opening_hours?.isOpen?.();
    const hours = formatOpeningHours(place.opening_hours?.weekday_text, openNow);
    const contact = place.formatted_phone_number || '연락처 정보 없음';
    const placeId = place.place_id;
    const name = place.name || '이름 없는 장소';
    const address = place.formatted_address || '주소 정보 없음';
    const actions = [
        place.website ? { label: '공식 사이트', url: place.website, external: true } : null,
        placeId ? { label: '점주로 등록하기', url: buildOwnerSignupUrl(placeId, name, address), external: false } : null,
    ].filter(Boolean);

    return {
        placeId,
        name,
        category: primaryType,
        address,
        description: place.business_status ? `상태: ${formatBusinessStatus(place.business_status)}` : '상세 정보가 준비되어 있습니다.',
        hours,
        contact,
        actions,
    };
}

function renderPlaceDetails(place) {
    selectedPlace = place;
    document.querySelector('#placeCategory').textContent = place.category;
    document.querySelector('#placeName').textContent = place.name;
    document.querySelector('#placeAddress').textContent = place.address;
    document.querySelector('#placeDescription').textContent = place.description;
    document.querySelector('#placeHours').innerHTML = place.hours;
    document.querySelector('#placeTip').textContent = place.contact;
    document.querySelector('#placeActions').innerHTML = place.actions.map((action) => (
        `<a class="action-link" href="${escapeHtml(action.url)}"${action.external ? ' target="_blank" rel="noreferrer"' : ''} aria-label="${escapeHtml(action.label)}${action.external ? ' 새 창 열기' : ''}">${escapeHtml(action.label)}</a>`
    )).join('');

    panel.classList.add('is-open');
    panel.setAttribute('aria-hidden', 'false');
    loadReviews(place.placeId);
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

function buildOwnerSignupUrl(placeId, placeName, placeAddress) {
    const params = new URLSearchParams({
        place_id: placeId,
        place_name: placeName,
        place_address: placeAddress,
    });

    return `/owner/signup/?${params.toString()}`;
}

function loadReviews(placeId) {
    if (!placeId) {
        renderReviews([]);
        return;
    }

    fetch(`/api/reviews/?place_id=${encodeURIComponent(placeId)}`)
        .then((response) => response.json())
        .then((payload) => {
            renderReviews(payload.data || []);
        })
        .catch(() => {
            showReviewMessage('리뷰를 불러오지 못했습니다.', true);
        });
}

function renderReviews(reviews) {
    if (!reviews.length) {
        reviewList.innerHTML = '<p class="review-empty">아직 등록된 리뷰가 없습니다.</p>';
        return;
    }

    const canReply = selectedPlace?.placeId && window.OWNER_PLACE_ID === selectedPlace.placeId;

    reviewList.innerHTML = reviews.map((review) => (
        `<article class="review-card" data-review-id="${review.id}">
            <div class="review-card-head">
                <strong>${escapeHtml(review.author_name)}</strong>
                <span>${buildOwnStars(review.rating)}</span>
            </div>
            <p>${escapeHtml(review.content)}</p>
            ${renderReplies(review.id, review.replies || [], canReply)}
            ${renderDeleteForm(review.id)}
            ${canReply ? renderReplyForm(review.id) : ''}
        </article>`
    )).join('');
}

function renderReplies(reviewId, replies, canManage) {
    if (!replies.length) {
        return '';
    }

    return `<div class="owner-replies">${replies.map((reply) => (
        `<div class="owner-reply">
            <div class="owner-reply-head">
                <strong>점주 답글</strong>
                ${canManage ? `<button class="delete-reply-button" type="button" data-review-id="${reviewId}" data-reply-id="${reply.id}">삭제</button>` : ''}
            </div>
            <p>${escapeHtml(reply.content)}</p>
        </div>`
    )).join('')}</div>`;
}

function renderReplyForm(reviewId) {
    return `<form class="reply-form" data-review-id="${reviewId}">
        <textarea name="content" rows="2" maxlength="2000" required></textarea>
        <button type="submit">답글</button>
    </form>`;
}

function renderDeleteForm(reviewId) {
    return `<div class="review-card-actions">
        <button class="delete-review-button" type="button" data-review-id="${reviewId}">삭제</button>
    </div>`;
}

function buildOwnStars(rating) {
    const value = Number(rating) || 0;
    return '★★★★★'.slice(0, value) + '☆☆☆☆☆'.slice(0, 5 - value);
}

function showReviewMessage(message, isError = false) {
    reviewMessage.textContent = message;
    reviewMessage.hidden = false;
    reviewMessage.classList.toggle('is-error', isError);
}

function openDeleteDialog(reviewId) {
    pendingDeleteReviewId = reviewId;
    deleteReviewPassword.value = '';
    deleteReviewDialog.hidden = false;
    deleteReviewPassword.focus();
}

function closeDeleteDialog() {
    pendingDeleteReviewId = null;
    deleteReviewDialog.hidden = true;
}

function formatOpeningHours(weekdayText, openNow) {
    if (!weekdayText?.length) {
        if (typeof openNow === 'boolean') {
            return `<p class="hours-fallback">${openNow ? '현재 영업 중' : '현재 영업 종료'}</p>`;
        }

        return '<p class="hours-fallback">운영 정보 없음</p>';
    }

    const todayIndex = new Date().getDay();
    const googleTodayIndex = todayIndex === 0 ? 6 : todayIndex - 1;

    return `<ul class="hours-list">${weekdayText.map((line, index) => {
        const [day, ...timeParts] = line.split(': ');
        const time = timeParts.join(': ') || '시간 정보 없음';
        const todayClass = index === googleTodayIndex ? ' class="is-today"' : '';

        return `<li${todayClass}>
            <span class="hours-day">${escapeHtml(day)}</span>
            <span class="hours-time">${escapeHtml(time)}</span>
        </li>`;
    }).join('')}</ul>`;
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

    reviewForm.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!selectedPlace?.placeId) {
            showReviewMessage('장소를 먼저 선택해주세요.', true);
            return;
        }

        fetch('/api/reviews/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                place_id: selectedPlace.placeId,
                place_name: selectedPlace.name,
                author_name: reviewAuthor.value,
                rating: reviewRating.value,
                content: reviewContent.value,
                delete_password: reviewDeletePassword.value,
            }),
        })
            .then((response) => response.json().then((payload) => ({ response, payload })))
            .then(({ response, payload }) => {
                if (!response.ok) {
                    throw new Error(payload.error || '리뷰 등록에 실패했습니다.');
                }

                reviewContent.value = '';
                reviewDeletePassword.value = '';
                showReviewMessage('리뷰가 등록되었습니다.');
                loadReviews(selectedPlace.placeId);
            })
            .catch((error) => {
                showReviewMessage(error.message, true);
            });
    });

    deleteReviewForm.addEventListener('submit', (event) => {
        event.preventDefault();
        if (!pendingDeleteReviewId) {
            return;
        }

        fetch(`/api/reviews/${pendingDeleteReviewId}/`, {
            method: 'DELETE',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ delete_password: deleteReviewPassword.value }),
        })
            .then((response) => response.json().then((payload) => ({ response, payload })))
            .then(({ response, payload }) => {
                if (!response.ok) {
                    throw new Error(payload.error || '리뷰 삭제에 실패했습니다.');
                }

                closeDeleteDialog();
                showReviewMessage('리뷰가 삭제되었습니다.');
                loadReviews(selectedPlace.placeId);
            })
            .catch((error) => {
                showReviewMessage(error.message, true);
            });
    });

    cancelDeleteReview.addEventListener('click', closeDeleteDialog);

    deleteReviewDialog.addEventListener('click', (event) => {
        if (event.target === deleteReviewDialog) {
            closeDeleteDialog();
        }
    });

    reviewList.addEventListener('click', (event) => {
        const deleteReplyButton = event.target.closest('.delete-reply-button');
        if (deleteReplyButton) {
            const reviewId = deleteReplyButton.dataset.reviewId;
            const replyId = deleteReplyButton.dataset.replyId;

            fetch(`/api/reviews/${reviewId}/reply/${replyId}/`, {
                method: 'DELETE',
            })
                .then((response) => response.json().then((payload) => ({ response, payload })))
                .then(({ response, payload }) => {
                    if (!response.ok) {
                        throw new Error(payload.error || '답글 삭제에 실패했습니다.');
                    }

                    showReviewMessage('답글이 삭제되었습니다.');
                    loadReviews(selectedPlace.placeId);
                })
                .catch((error) => {
                    showReviewMessage(error.message, true);
                });
            return;
        }

        const deleteButton = event.target.closest('.delete-review-button');
        if (deleteButton) {
            openDeleteDialog(deleteButton.dataset.reviewId);
            return;
        }
    });

    reviewList.addEventListener('submit', (event) => {
        const form = event.target.closest('.reply-form');
        if (!form) {
            return;
        }

        event.preventDefault();
        const reviewId = form.dataset.reviewId;
        const content = form.elements.content.value;

        fetch(`/api/reviews/${reviewId}/reply/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ content }),
        })
            .then((response) => response.json().then((payload) => ({ response, payload })))
            .then(({ response, payload }) => {
                if (!response.ok) {
                    throw new Error(payload.error || '답글 저장에 실패했습니다.');
                }

                showReviewMessage('답글이 저장되었습니다.');
                loadReviews(selectedPlace.placeId);
            })
            .catch((error) => {
                showReviewMessage(error.message, true);
            });
    });

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
            if (!deleteReviewDialog.hidden) {
                closeDeleteDialog();
                return;
            }
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
