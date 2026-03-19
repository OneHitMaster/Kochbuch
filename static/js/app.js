const state = {
    activeRecipe: null,
    activeMultiplier: 1,
    homeMealSlotFilter: "Alle",
};

const MEAL_SLOTS = ["Frühstück", "Mittag", "Abend", "Snacks"];

const heartSvg = `<svg class="heart-icon" viewBox="0 0 24 24"><path d="M12 21s-6.72-4.35-9.38-8.39C.24 9.17 1.42 4.9 5.14 3.58A5.28 5.28 0 0 1 12 6.1a5.28 5.28 0 0 1 6.86-2.52c3.72 1.32 4.9 5.59 2.52 9.03C18.72 16.65 12 21 12 21z"/></svg>`;

function toastEl() {
    return document.getElementById("toast");
}

async function api(url, options = {}) {
    const body = options.body;
    const headers = { ...(options.headers || {}) };
    const isFormData = typeof FormData !== "undefined" && body instanceof FormData;

    if (body !== undefined && body !== null && !isFormData && headers["Content-Type"] === undefined) {
        headers["Content-Type"] = "application/json";
    }

    const response = await fetch(url, {
        ...options,
        headers,
    });
    if (!response.ok) {
        const err = await response.json().catch(() => ({}));
        throw new Error(err.error || "Request failed");
    }
    // Some endpoints may return empty payloads in the future.
    return response.json().catch(() => ({}));
}

function showToast(message) {
    const node = toastEl();
    if (!node) return;
    node.textContent = message;
    node.classList.remove("hidden");
    clearTimeout(showToast.timer);
    showToast.timer = setTimeout(() => node.classList.add("hidden"), 1800);
}

function withLoading(container) {
    container.innerHTML = `<div class="loader">Lädt...</div>`;
}

function formatIngredientText(item, multiplier = 1) {
    const amount = Number(item.amount || 1) * multiplier;
    const rounded = Math.round(amount * 100) / 100;
    const amountText = Number.isInteger(rounded) ? rounded : rounded.toFixed(2);
    return `${amountText} ${item.unit || ""} ${item.name || item.ingredient_name}`.trim();
}

function renderRecipeCard(recipe) {
    return `
        <article class="card recipe-card">
            <a class="recipe-hero-link" href="/recipe/${recipe.id}">
                <img class="recipe-image" src="${recipe.image_url}" alt="${recipe.title}">
            </a>
            <div class="recipe-meta">
                <div>
                    <a class="recipe-title-link" href="/recipe/${recipe.id}">
                        <h3 class="recipe-title">${recipe.title}</h3>
                    </a>
                    <span class="pill">${recipe.meal_slot}</span>
                </div>
            </div>
        </article>
    `;
}

function renderRecipes(container, recipes) {
    container.innerHTML = recipes.map(renderRecipeCard).join("");
}

function renderShopping(container, items, emptyNode) {
    container.innerHTML = items
        .map(
            (item) => `
        <label class="check-item ${item.bought ? "done" : ""}">
            <input type="checkbox" data-shopping-id="${item.id}" ${item.bought ? "checked" : ""}>
            <span>${formatIngredientText(item)}</span>
        </label>
    `
        )
        .join("");
    emptyNode.classList.toggle("hidden", items.length > 0);
    if (items.length === 0) container.innerHTML = "";
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

let currentImageObjectUrl = null;

function getCurrentPreviewImageUrl() {
    const fileInput = document.getElementById("newImageFile");
    const imageUrlInput = document.getElementById("newImage");

    if (fileInput && fileInput.files && fileInput.files[0]) {
        if (!currentImageObjectUrl) {
            currentImageObjectUrl = URL.createObjectURL(fileInput.files[0]);
        }
        return currentImageObjectUrl;
    }

    // If no file is selected, revoke previously created object URLs.
    if (currentImageObjectUrl) {
        URL.revokeObjectURL(currentImageObjectUrl);
        currentImageObjectUrl = null;
    }

    return imageUrlInput?.value?.trim() || "";
}

function renderAddPreview() {
    const title = document.getElementById("newTitle")?.value || "Dein Rezept";
    const mealSlot = document.getElementById("newMealSlot")?.value || "Abend";
    const image = getCurrentPreviewImageUrl() || "/static/images/placeholder.svg";
    const preview = document.getElementById("recipePreview");
    if (!preview) return;
    preview.innerHTML = `
        <img src="${image}" alt="${title}">
        <div class="preview-card-body">
            <h4>${title}</h4>
            <span class="pill">${mealSlot}</span>
        </div>
    `;
}

function initHomeMealSlotTabs() {
    const tabs = document.getElementById("homeMealSlotTabs");
    if (!tabs) return;

    const buttons = [{ label: "Alle", value: "Alle" }, ...MEAL_SLOTS.map((s) => ({ label: s, value: s }))];
    tabs.innerHTML = buttons
        .map(
            (b) =>
                `<button class="serving-chip ${state.homeMealSlotFilter === b.value ? "active" : ""}" data-meal-slot-filter="${b.value}">
                    ${b.label}
                </button>`
        )
        .join("");

    tabs.onclick = (event) => {
        const btn = event.target.closest("[data-meal-slot-filter]");
        if (!btn) return;
        state.homeMealSlotFilter = btn.dataset.mealSlotFilter;
        initHomeMealSlotTabs();
        loadHome().catch((err) => showToast(err.message || "Fehler beim Laden"));
    };
}

async function loadHome() {
    const list = document.getElementById("homeRecipeList");
    const empty = document.getElementById("homeEmptyState");
    if (!list) return;

    withLoading(list);

    const recipes = await api("/api/recipes");

    const filtered =
        state.homeMealSlotFilter === "Alle"
            ? recipes
            : recipes.filter((r) => String(r.meal_slot || "").toLowerCase() === String(state.homeMealSlotFilter).toLowerCase());

    if (filtered.length === 0) {
        list.innerHTML = "";
        empty.classList.toggle("hidden", false);
        return;
    }

    // When selecting "Alle", group cards by meal slot.
    if (state.homeMealSlotFilter === "Alle") {
        const groupedHtml = [];
        for (const slot of MEAL_SLOTS) {
            const group = recipes.filter((r) => r.meal_slot === slot);
            if (!group.length) continue;
            groupedHtml.push(`<div class="slot-header">${slot}</div>`);
            groupedHtml.push(group.map(renderRecipeCard).join(""));
        }
        // Also include any unexpected meal_slot values.
        const known = new Set(MEAL_SLOTS);
        const other = recipes.filter((r) => !known.has(r.meal_slot));
        if (other.length) {
            groupedHtml.push(`<div class="slot-header">Sonstiges</div>`);
            groupedHtml.push(other.map(renderRecipeCard).join(""));
        }
        list.innerHTML = groupedHtml.join("");
    } else {
        list.innerHTML = filtered.map(renderRecipeCard).join("");
    }

    empty.classList.toggle("hidden", filtered.length > 0);
}

async function loadFavorites() {
    const list = document.getElementById("favoriteRecipeList");
    const empty = document.getElementById("favoritesEmptyState");
    if (!list) return;
    withLoading(list);
    const recipes = await api("/api/favorites");
    list.innerHTML = recipes.map(renderRecipeCard).join("");
    empty.classList.toggle("hidden", recipes.length > 0);
    if (recipes.length === 0) list.innerHTML = "";
}

async function loadShopping() {
    const list = document.getElementById("shoppingList");
    const empty = document.getElementById("shoppingEmptyState");
    if (!list) return;
    withLoading(list);
    const items = await api("/api/shopping-list");
    state.shopping = items;
    renderShopping(list, items, empty);
}

async function toggleFavorite(btn) {
    const recipeId = btn.dataset.favId;
    const res = await api(`/api/favorites/${recipeId}`, { method: "POST" });
    const isFav = !!res.is_favorite;
    btn.classList.toggle("active", isFav);
    // Keep favorites page in sync.
    if (document.body.dataset.page === "favorites") {
        await loadFavorites();
    }
    showToast("Favorit aktualisiert");
}

async function runSearch() {
    const params = new URLSearchParams({
        q: document.getElementById("searchName")?.value?.trim() || "",
        ingredient: document.getElementById("searchIngredient")?.value?.trim() || "",
        category: document.getElementById("searchCategory")?.value?.trim() || "",
    });
    state.lastSearch = params.toString();
    const results = document.getElementById("searchResults");
    if (!results) return;
    withLoading(results);
    const data = await api(`/api/recipes?${params.toString()}`);
    if (data.length === 0) {
        results.innerHTML = `<div class="empty-state">Keine passenden Rezepte gefunden.</div>`;
        return;
    }
    results.innerHTML = data.map(renderRecipeCard).join("");
}

async function runSuggestions() {
    const ingredients = document.getElementById("aiIngredientInput")?.value?.trim() || "";
    const results = document.getElementById("searchResults");
    if (!results) return;
    withLoading(results);
    const suggestions = await api("/api/suggest-recipes", {
        method: "POST",
        body: JSON.stringify({ ingredients }),
    });
    if (!suggestions.length) {
        results.innerHTML = `<div class="empty-state">Noch keine Vorschläge. Probier andere Zutaten.</div>`;
        return;
    }
    results.innerHTML = suggestions
        .map(
            (item) => `
        <div class="card" style="margin-bottom: 14px; padding: 12px;">
            <div class="muted">Übereinstimmung: ${(item.score * 100).toFixed(0)}%</div>
            ${renderRecipeCard(item.recipe)}
        </div>
    `
        )
        .join("");
}

function renderRecipeDetail(recipe) {
    state.activeRecipe = recipe;
    const hero = document.getElementById("detailHero");
    const title = document.getElementById("detailTitle");
    const category = document.getElementById("detailCategory");
    const mealSlotEl = document.getElementById("detailMealSlot");
    const servingControls = document.getElementById("servingControls");
    const servingInfo = document.getElementById("servingInfo");
    const ingredientsEl = document.getElementById("detailIngredients");
    const stepsEl = document.getElementById("detailSteps");

    if (!hero || !title || !category || !mealSlotEl || !servingControls || !ingredientsEl || !stepsEl) return;

    const baseServings = recipe.servings || 2;
    const multiplier = state.activeMultiplier;

    hero.src = recipe.image_url;
    hero.alt = recipe.title;
    title.textContent = recipe.title;
    category.textContent = recipe.category;
    mealSlotEl.textContent = recipe.meal_slot;

    servingControls.innerHTML = [1, 2, 3, 4]
        .map(
            (m) => `
            <button class="serving-chip ${m === multiplier ? "active" : ""}" data-multiplier="${m}">
                ${m}x
            </button>
        `
        )
        .join("");

    servingInfo.textContent = `Basisportionen: ${baseServings} | Jetzt: ${baseServings * multiplier}`;

    ingredientsEl.innerHTML = recipe.ingredients
        .map((item) => {
            return `
                <div class="check-item">
                    <span>${formatIngredientText(item, multiplier)}</span>
                </div>
            `;
        })
        .join("");

    stepsEl.innerHTML = recipe.steps.map((s) => `<li>${s}</li>`).join("");
}

async function initRecipeDetail() {
    const recipeId = window.__COOKMIND_RECIPE_ID__;
    if (!recipeId) return;
    const servingControls = document.getElementById("servingControls");
    if (!servingControls) return;

    state.activeMultiplier = 1;
    const recipe = await api(`/api/recipes/${recipeId}`);
    renderRecipeDetail(recipe);

    servingControls.addEventListener("click", (event) => {
        const servingBtn = event.target.closest("[data-multiplier]");
        if (!servingBtn) return;
        state.activeMultiplier = Number(servingBtn.dataset.multiplier);
        renderRecipeDetail(recipe);
    });

    const deleteBtn = document.getElementById("deleteRecipeBtn");
    if (deleteBtn) {
        deleteBtn.addEventListener("click", async () => {
            const ok = window.confirm("Rezept wirklich löschen?");
            if (!ok) return;
            try {
                await api(`/api/recipes/${recipe.id}`, { method: "DELETE" });
                showToast("Rezept gelöscht");
                window.location.href = "/";
            } catch (err) {
                showToast(err.message || "Löschen fehlgeschlagen");
            }
        });
    }
}

async function initAddRecipe() {
    renderAddPreview();
    const fieldsToRerender = ["newTitle", "newCategory", "newMealSlot", "newImage", "newServings", "newIngredients", "newSteps"];
    fieldsToRerender.forEach((id) => {
        const node = document.getElementById(id);
        if (node) node.addEventListener("input", () => renderAddPreview());
    });

    const mealSlotSelect = document.getElementById("newMealSlot");
    if (mealSlotSelect) mealSlotSelect.addEventListener("change", () => renderAddPreview());

    const fileInput = document.getElementById("newImageFile");
    if (fileInput) {
        fileInput.addEventListener("change", () => {
            // Ensure the preview updates when a different file is chosen.
            if (currentImageObjectUrl) {
                URL.revokeObjectURL(currentImageObjectUrl);
                currentImageObjectUrl = null;
            }
            renderAddPreview();
        });
    }

    const saveBtn = document.getElementById("saveRecipeBtn");
    if (!saveBtn) return;

    saveBtn.addEventListener("click", async () => {
        try {
            const formData = new FormData();
            formData.append("title", document.getElementById("newTitle").value.trim());
            formData.append("category", document.getElementById("newCategory").value.trim() || "General");
            formData.append("meal_slot", document.getElementById("newMealSlot").value || "Abend");
            formData.append("servings", String(Number(document.getElementById("newServings").value || 2)));
            formData.append("ingredients", JSON.stringify(parseIngredientsInput(document.getElementById("newIngredients").value)));
            formData.append("steps", JSON.stringify(parseStepsInput(document.getElementById("newSteps").value)));

            const imageUrl = document.getElementById("newImage")?.value?.trim() || "";
            if (imageUrl) formData.append("image_url", imageUrl);

            const file = document.getElementById("newImageFile")?.files?.[0];
            if (file) formData.append("image_file", file);

            await api("/api/recipes", { method: "POST", body: formData });
            showToast("Rezept erstellt");
            window.location.href = "/";
        } catch (err) {
            showToast(err.message || "Konnte Rezept nicht speichern");
        }
    });
}

async function initEditRecipe() {
    const recipeId = window.__COOKMIND_EDIT_RECIPE_ID__;
    if (!recipeId) return;

    const recipe = await api(`/api/recipes/${recipeId}`);

    // Populate form
    document.getElementById("newTitle").value = recipe.title || "";
    document.getElementById("newCategory").value = recipe.category || "";
    document.getElementById("newMealSlot").value = recipe.meal_slot || "Abend";
    document.getElementById("newServings").value = recipe.servings || 2;
    document.getElementById("newImage").value = recipe.image_url || "";

    const ingredientsText = (recipe.ingredients || [])
        .map((i) => `${i.name}|${i.amount}|${i.unit || ""}`)
        .join("\n");
    document.getElementById("newIngredients").value = ingredientsText;
    document.getElementById("newSteps").value = (recipe.steps || []).join("\n");

    // Clear file input and reset preview object URL.
    const fileInput = document.getElementById("newImageFile");
    if (fileInput) fileInput.value = "";
    if (currentImageObjectUrl) {
        URL.revokeObjectURL(currentImageObjectUrl);
        currentImageObjectUrl = null;
    }

    renderAddPreview();

    const mealSlotSelect = document.getElementById("newMealSlot");
    if (mealSlotSelect) mealSlotSelect.addEventListener("change", () => renderAddPreview());

    ["newTitle", "newCategory", "newMealSlot", "newImage"].forEach((id) => {
        const node = document.getElementById(id);
        if (node) node.addEventListener("input", () => renderAddPreview());
    });
    if (fileInput) {
        fileInput.addEventListener("change", () => {
            if (currentImageObjectUrl) {
                URL.revokeObjectURL(currentImageObjectUrl);
                currentImageObjectUrl = null;
            }
            renderAddPreview();
        });
    }

    const saveBtn = document.getElementById("saveRecipeBtn");
    if (!saveBtn) return;

    saveBtn.addEventListener("click", async () => {
        try {
            const formData = new FormData();
            formData.append("title", document.getElementById("newTitle").value.trim());
            formData.append("category", document.getElementById("newCategory").value.trim() || "General");
            formData.append("meal_slot", document.getElementById("newMealSlot").value || "Abend");
            formData.append("servings", String(Number(document.getElementById("newServings").value || 2)));
            formData.append("ingredients", JSON.stringify(parseIngredientsInput(document.getElementById("newIngredients").value)));
            formData.append("steps", JSON.stringify(parseStepsInput(document.getElementById("newSteps").value)));

            const imageUrl = document.getElementById("newImage")?.value?.trim() || "";
            if (imageUrl) formData.append("image_url", imageUrl);

            const file = document.getElementById("newImageFile")?.files?.[0];
            if (file) formData.append("image_file", file);

            await api(`/api/recipes/${recipeId}`, { method: "PUT", body: formData });
            showToast("Änderungen gespeichert");
            window.location.href = `/recipe/${recipeId}`;
        } catch (err) {
            showToast(err.message || "Konnte Änderungen nicht speichern");
        }
    });
}

async function initMealPlan() {
    const grid = document.getElementById("mealPlanGrid");
    const emptyState = document.getElementById("mealPlanEmptyState");
    if (!grid) return;

    withLoading(grid);

    const [recipes, mealPlan] = await Promise.all([api("/api/recipes"), api("/api/meal-plan")]);

    const recipesBySlot = {};
    for (const slot of MEAL_SLOTS) recipesBySlot[slot] = [];
    (recipes || []).forEach((r) => {
        if (recipesBySlot[r.meal_slot]) recipesBySlot[r.meal_slot].push(r);
    });

    let hasAny = false;
    (mealPlan || []).forEach((day) => {
        if (!day || !day.items) return;
        for (const slot of MEAL_SLOTS) {
            if (day.items[slot]) hasAny = true;
        }
    });

    if (emptyState) emptyState.classList.toggle("hidden", hasAny);
    if (!hasAny) {
        grid.innerHTML = "";
        return;
    }

    const dayLabels = ["Mo", "Di", "Mi", "Do", "Fr", "Sa", "So"];

    grid.innerHTML = (mealPlan || [])
        .map((day) => {
            const dayIndex = day.day_index;
            const label = dayLabels[dayIndex] || `Tag ${dayIndex + 1}`;
            return `
                <div class="card" style="padding: 14px; margin-bottom: 14px;">
                    <h3 style="margin: 0 0 10px;">${label}</h3>
                    ${MEAL_SLOTS.map((slot) => {
                        const currentId = day.items ? day.items[slot] : null;
                        const options = (recipesBySlot[slot] || [])
                            .map((r) => {
                                const selected = currentId !== null && String(r.id) === String(currentId);
                                return `<option value="${r.id}" ${selected ? "selected" : ""}>${r.title}</option>`;
                            })
                            .join("");
                        return `
                            <div style="margin-bottom: 10px;">
                                <div class="muted" style="margin-bottom: 6px;">${slot}</div>
                                <select class="input mealplan-select" data-day-index="${dayIndex}" data-meal-slot="${slot}">
                                    <option value="">Kein Rezept</option>
                                    ${options}
                                </select>
                            </div>
                        `;
                    }).join("")}
                </div>
            `;
        })
        .join("");

    grid.addEventListener("change", async (event) => {
        const select = event.target.closest("select.mealplan-select");
        if (!select) return;

        const dayIndex = Number(select.dataset.dayIndex);
        const mealSlot = select.dataset.mealSlot;
        const val = select.value;
        const recipeId = val ? Number(val) : null;

        try {
            await api("/api/meal-plan", {
                method: "POST",
                body: JSON.stringify({
                    entries: [{ day_index: dayIndex, meal_slot: mealSlot, recipe_id: recipeId }],
                }),
            });
            showToast("Meal-Plan gespeichert");
        } catch (err) {
            showToast(err.message || "Speichern fehlgeschlagen");
        }
    });
}

async function initSettings() {
    const btn = document.getElementById("resetMealPlanBtn");
    if (!btn) return;

    btn.addEventListener("click", async () => {
        const ok = window.confirm("Meal-Plan wirklich löschen?");
        if (!ok) return;

        try {
            await api("/api/meal-plan/reset", { method: "POST" });
            showToast("Meal-Plan gelöscht");
            window.location.href = "/meal-plan";
        } catch (err) {
            showToast(err.message || "Reset fehlgeschlagen");
        }
    });
}

function bindGlobalEvents() {
    // Global handlers are intentionally minimal.
    // Meal-Plan uses page-local event binding.
}

async function init() {
    bindGlobalEvents();
    const page = document.body.dataset.page || "home";

    if (page === "home") {
        initHomeMealSlotTabs();
        await loadHome();
    }
    if (page === "mealplan") {
        await initMealPlan();
    }
    if (page === "settings") {
        await initSettings();
    }

    if (page === "search") {
        const searchBtn = document.getElementById("searchBtn");
        const suggestBtn = document.getElementById("suggestBtn");
        if (searchBtn) searchBtn.addEventListener("click", () => runSearch().catch((err) => showToast(err.message)));
        if (suggestBtn)
            suggestBtn.addEventListener("click", () => runSuggestions().catch((err) => showToast(err.message)));
    }

    if (page === "recipe") await initRecipeDetail();
    if (page === "add") await initAddRecipe();
    if (page === "edit") await initEditRecipe();
}

init().catch((err) => showToast(err.message || "Initialisierung fehlgeschlagen"));
