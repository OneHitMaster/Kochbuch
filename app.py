import os

from flask import render_template

from cookmind import create_app
from cookmind.db import close_db

app = create_app()


@app.teardown_appcontext
def _close_db(exception):
    close_db(exception)


@app.route("/")
def home():
    return render_template("home.html", active_page="home")


@app.route("/search")
def search():
    return render_template("search.html", active_page="search")


@app.route("/favorites")
def favorites():
    return render_template("favorites.html", active_page="favorites")


@app.route("/shopping")
def shopping():
    return render_template("shopping.html", active_page="shopping")


@app.route("/recipe/<int:recipe_id>")
def recipe_detail(recipe_id: int):
    return render_template("recipe_detail.html", active_page="recipe", recipe_id=recipe_id)


@app.route("/recipes/new")
def add_recipe():
    return render_template("add_recipe.html", active_page="add")


if __name__ == "__main__":
    # Pi-friendly: default debug off. Enable with `COOKMIND_DEBUG=1`.
    debug = os.environ.get("COOKMIND_DEBUG", "0") == "1"
    app.run(host="0.0.0.0", port=5000, debug=debug)
