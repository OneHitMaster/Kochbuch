const state = {
    recipes: [],
    favorites: [],
    shopping: [],
    activeRecipe: null,
};

const el = {
    screens: {
        home: document.getElementById("screen-home"),
        search: document.getElementById("screen-search"),
        favorites: document.getElementById("screen-favorites"),
        shopping: document.getElementById("screen-shopping"),
    },
    navItems: document.querySelectorAll(".nav-item"),
    homeRecipeList: document.getElementById("homeRecipeList"),
    favoriteRecipeList: document.getElementById("favoriteRecipeList"),
    shoppingList: document.getElementById("shoppingList"),
    searchResults: document.getElementById("searchResults"),
    homeEmptyState: document.getElementById("homeEmptyState"),
    favoritesEmptyState: document.getElementById("favoritesEmptyState"),
    shoppingEmptyState: document.getElementById("shoppingEmptyState"),
    recipeModal: document.getElementById("recipeModal"),
    addRecipeModal: document.getElementById("addRecipeModal"),
    recipeDetailContent: document.getElementById("recipeDetailContent"),
    closeRecipeModal: document.getElementById("closeRecipeModal"),
    closeAddRecipeModal: document.getElementById("closeAddRecipeModal"),
    openAddRecipeBtn: document.getElementById("openAddRecipeBtn"),
    saveRecipeBtn: document.getElementById("saveRecipeBtn"),
    toast: document.getElementById("toast"),
    searchName: document.getElementById("searchName"),
    searchIngredient: document.getElementById("searchIngredient"),
    searchCategory: document.getElementById("searchCategory"),
    searchBtn: document.getElementById("searchBtn"),
    suggestBtn: document.getElementById("suggestBtn"),
    aiIngredientInput: document.getElementById("aiIngredientInput"),
    preview: document.getElementById("recipePreview"),
    form: {
        title: document.getElementById("newTitle"),
        category: document.getElementById("newCategory"),
        image: document.getElementById("newImage"),
        servings: document.getElementById("newServings"),
        ingredients: document.getElementById("newIngredients"),
        steps: document.getElementById("newSteps"),
    },
};

const heartSvg = `<svg class="heart-icon" viewBox="0 0 24 24"><path d="M12 21s-6.72-4.35-9.38-8.39C.24 9.17 1.42 4.9 5.14 3.58A5.28 5.28 0 0 1 12 6.1a5.28 5.28 0 0 1 6.86-2.52c3.72 1.32 4.9 5.59 2.52 9.03C18.72 16.65 12 21 12 21z"/></svg>`;

async function api(url, options = {}) {
    const response = await fetch(url, {
        headers: { "Content-Type": "application/json" },
        ...options,
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || "Request failed");
    }
    return response.json();
}

function showToast(message) {
    el.toast.textContent = message;
    el.toast.classList.remove("hidden");
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => el.toast.classList.add("hidden"), 1800);
}

function withLoading(container) {
    container.innerHTML = `<div class="loader">Loading...</div>`;
}

function switchScreen(target) {
    Object.entries(el.screens).forEach(([key, node]) => {
        node.classList.toggle("active", key === target);
    });
    el.navItems.forEach((btn) => btn.classList.toggle("active", btn.dataset.target === target));
}

function renderRecipeCard(recipe) {
    return `
        <article class="card recipe-card" data-open-recipe="${recipe.id}">
            <img class="recipe-image" src="${recipe.image_url}" alt="${recipe.title}">
            <div class="recipe-meta">
                <div>
                    <h3 class="recipe-title">${recipe.title}</h3>
                    <span class="pill">${recipe.category}</span>
                </div>
                <button class="favorite-btn ${recipe.is_favorite ? "active" : ""}" data-fav-id="${recipe.id}">
                    ${heartSvg}
                </button>
            </div>
        </article>
    `;
}

function renderRecipes(container, recipes, emptyNode) {
    container.innerHTML = recipes.map(renderRecipeCard).join("");
    emptyNode.classList.toggle("hidden", recipes.length > 0);
    if (recipes.length === 0) {
        container.innerHTML = "";
    }
}

function formatIngredientText(item, multiplier = 1) {
    const amount = Number(item.amount || 1) * multiplier;
    const rounded = Math.round(amount * 100) / 100;
    const amountText = Number.isInteger(rounded) ? rounded : rounded.toFixed(2);
    return `${amountText} ${item.unit || ""} ${item.name || item.ingredient_name}`.trim();
}

function renderShopping() {
    const shopping = state.shopping;
    el.shoppingList.innerHTML = shopping
        .map(
            (item) => `
        <label class="check-item ${item.bought ? "done" : ""}">
            <input type="checkbox" data-shopping-id="${item.id}" ${item.bought ? "checked" : ""}>
            <span>${formatIngredientText(item)}</span>
        </label>
    `
        )
        .join("");
    el.shoppingEmptyState.classList.toggle("hidden", shopping.length > 0);
}

function renderPreview() {
    const title = el.form.title.value || "Your Recipe Title";
    const category = el.form.category.value || "Category";
    const image = el.form.image.value || "https://images.unsplash.com/photo-1495195134817-aeb325a55b65?auto=format&fit=crop&w=1200&q=80";
    el.preview.innerHTML = `
        <img src="${image}" alt="${title}">
        <div class="preview-card-body">
            <h4>${title}</h4>
            <span class="pill">${category}</span>
        </div>
    `;
}

async function loadRecipes() {
    withLoading(el.homeRecipeList);
    state.recipes = await api("/api/recipes");
    renderRecipes(el.homeRecipeList, state.recipes, el.homeEmptyState);
}

async function loadFavorites() {
    state.favorites = await api("/api/favorites");
    renderRecipes(el.favoriteRecipeList, state.favorites, el.favoritesEmptyState);
}

async function loadShopping() {
    state.shopping = await api("/api/shopping-list");
    renderShopping();
}

async function toggleFavorite(recipeId) {
    await api(`/api/favorites/${recipeId}`, { method: "POST" });
    showToast("Favorite updated");
    await Promise.all([loadRecipes(), loadFavorites()]);
}

function openRecipeModal(recipe) {
    state.activeRecipe = recipe;
    const baseServings = recipe.servings || 2;
    let activeMultiplier = 1;

    const renderDetail = () => {
        el.recipeDetailContent.innerHTML = `
            <img class="detail-hero" src="${recipe.image_url}" alt="${recipe.title}">
            <h2>${recipe.title}</h2>
            <span class="pill">${recipe.category}</span>
            <h3>Servings</h3>
            <div class="serving-controls">
                ${[1, 2, 3, 4]
                    .map(
                        (m) =>
                            `<button class="serving-chip ${m === activeMultiplier ? "active" : ""}" data-multiplier="${m}">
                                ${m}x
                            </button>`
                    )
                    .join("")}
            </div>
            <p class="muted">Base servings: ${baseServings} | Now: ${baseServings * activeMultiplier}</p>
            <h3>Ingredients</h3>
            <div class="checklist">
                ${recipe.ingredients
                    .map(
                        (item, idx) => `
                    <label class="check-item">
                        <input type="checkbox" data-ingredient-check="${idx}">
                        <span>${formatIngredientText(item, activeMultiplier)}</span>
                    </label>
                `
                    )
                    .join("")}
            </div>
            <h3>Instructions</h3>
            <ol>
                ${recipe.steps.map((step) => `<li>${step}</li>`).join("")}
            </ol>
            <button class="btn btn-primary full-width" id="addToShoppingBtn">
                Add ingredients to shopping list
            </button>
        `;
    };

    renderDetail();
    el.recipeModal.classList.remove("hidden");

    el.recipeDetailContent.onclick = async (event) => {
        const servingBtn = event.target.closest("[data-multiplier]");
        if (servingBtn) {
            activeMultiplier = Number(servingBtn.dataset.multiplier);
            renderDetail();
            return;
        }
        if (event.target.id === "addToShoppingBtn") {
            await api(`/api/shopping-list/from-recipe/${recipe.id}`, { method: "POST" });
            await loadShopping();
            showToast("Added to shopping list");
        }
    };
}

function closeRecipeModal() {
    el.recipeModal.classList.add("hidden");
    el.recipeDetailContent.innerHTML = "";
    state.activeRecipe = null;
}

function parseIngredientsInput(raw) {
    return raw
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean)
        .map((line) => {
            const [name, amount, unit] = line.split("|").map((x) => x.trim());
            return { name, amount: Number(amount || 1), unit: unit || "" };
        });
}

function parseStepsInput(raw) {
    return raw
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
}

async function saveRecipe() {
    const payload = {
        title: el.form.title.value.trim(),
        category: el.form.category.value.trim() || "General",
        image_url: el.form.image.value.trim(),
        servings: Number(el.form.servings.value || 2),
        ingredients: parseIngredientsInput(el.form.ingredients.value),
        steps: parseStepsInput(el.form.steps.value),
    };
    await api("/api/recipes", {
        method: "POST",
        body: JSON.stringify(payload),
    });
    showToast("Recipe created");
    el.addRecipeModal.classList.add("hidden");
    Object.values(el.form).forEach((input) => {
        input.value = "";
    });
    el.form.servings.value = 2;
    renderPreview();
    await Promise.all([loadRecipes(), loadFavorites()]);
}

async function runSearch() {
    const params = new URLSearchParams({
        q: el.searchName.value.trim(),
        ingredient: el.searchIngredient.value.trim(),
        category: el.searchCategory.value.trim(),
    });
    const data = await api(`/api/recipes?${params.toString()}`);
    renderRecipes(el.searchResults, data, document.createElement("div"));
    if (data.length === 0) {
        el.searchResults.innerHTML = `<div class="empty-state">No matching recipes found.</div>`;
    }
}

async function runSuggestions() {
    const ingredients = el.aiIngredientInput.value.trim();
    const suggestions = await api("/api/suggest-recipes", {
        method: "POST",
        body: JSON.stringify({ ingredients }),
    });
    if (!suggestions.length) {
        el.searchResults.innerHTML = `<div class="empty-state">No suggestions yet. Try more ingredients.</div>`;
        return;
    }
    el.searchResults.innerHTML = suggestions
        .map(
            (item) => `
        <article class="card">
            <p class="muted">Match score: ${(item.score * 100).toFixed(0)}%</p>
            ${renderRecipeCard(item.recipe)}
        </article>
    `
        )
        .join("");
}

function bindGlobalEvents() {
    el.navItems.forEach((item) => {
        item.addEventListener("click", () => switchScreen(item.dataset.target));
    });

    document.body.addEventListener("click", (event) => {
        const favBtn = event.target.closest("[data-fav-id]");
        if (favBtn) {
            event.stopPropagation();
            toggleFavorite(favBtn.dataset.favId);
            return;
        }
        const card = event.target.closest("[data-open-recipe]");
        if (card) {
            const recipe = [...state.recipes, ...state.favorites].find((r) => String(r.id) === card.dataset.openRecipe);
            if (recipe) openRecipeModal(recipe);
        }

        const shopToggle = event.target.closest("[data-shopping-id]");
        if (shopToggle) {
            api(`/api/shopping-list/${shopToggle.dataset.shoppingId}/toggle`, { method: "POST" })
                .then(loadShopping)
                .catch((err) => showToast(err.message));
        }
    });

    el.closeRecipeModal.addEventListener("click", closeRecipeModal);
    el.recipeModal.addEventListener("click", (event) => {
        if (event.target === el.recipeModal) closeRecipeModal();
    });

    el.openAddRecipeBtn.addEventListener("click", () => el.addRecipeModal.classList.remove("hidden"));
    el.closeAddRecipeModal.addEventListener("click", () => el.addRecipeModal.classList.add("hidden"));
    el.saveRecipeBtn.addEventListener("click", () => {
        saveRecipe().catch((err) => showToast(err.message));
    });

    Object.values(el.form).forEach((input) => input.addEventListener("input", renderPreview));

    el.searchBtn.addEventListener("click", () => runSearch().catch((err) => showToast(err.message)));
    el.suggestBtn.addEventListener("click", () => runSuggestions().catch((err) => showToast(err.message)));
}

async function init() {
    bindGlobalEvents();
    renderPreview();
    await Promise.all([loadRecipes(), loadFavorites(), loadShopping()]);
}

init().catch((err) => {
    showToast(err.message || "Initialization failed");
});
