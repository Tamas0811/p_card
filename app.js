// Populate the scrollable list on page load (sorted alphabetically)
document.addEventListener("DOMContentLoaded", async () => {
  const selectEl = document.getElementById("pokemonSelect");
  try {
    // Fetches the first 151 original Pokémon
    const res = await fetch("https://pokeapi.co/api/v2/pokemon?limit=151");
    const data = await res.json();

    // Sort Pokémon alphabetically by name
    const sortedPokemon = data.results.sort((a, b) => a.name.localeCompare(b.name));

    selectEl.innerHTML = "";
    sortedPokemon.forEach((poke) => {
      const option = document.createElement("option");
      option.value = poke.name;
      option.textContent = poke.name.toUpperCase();
      selectEl.appendChild(option);
    });
  } catch (err) {
    selectEl.innerHTML = "<option>Failed to load Pokémon</option>";
  }
});

async function checkEvolution(selectedName) {
  const input = selectedName || document.getElementById('pokemonSelect').value;
  const resultDiv = document.getElementById('result');
  if (!input) return;

  resultDiv.innerHTML = "<p>Searching...</p>";

  try {
    const response = await fetch(`https://pokeapi.co/api/v2/pokemon/${input}`);
    if (!response.ok) throw new Error("Pokémon not found");
    const data = await response.json();

    const getTypes = (poke) => poke.types.map(t => t.type.name).join(', ');
    const getBst = (poke) => poke.stats.reduce((sum, s) => sum + s.base_stat, 0);

    const currentTypes = getTypes(data);
    const currentBst = getBst(data);

    const speciesResponse = await fetch(data.species.url);
    const speciesData = await speciesResponse.json();

    const evoResponse = await fetch(speciesData.evolution_chain.url);
    const evoData = await evoResponse.json();

    let chain = evoData.chain;
    let evolvesTo = null;

    if (chain.species.name === input && chain.evolves_to.length > 0) {
      evolvesTo = chain.evolves_to[0].species.name;
    } else if (chain.evolves_to.length > 0) {
      for (let sub of chain.evolves_to) {
        if (sub.species.name === input && sub.evolves_to.length > 0) {
          evolvesTo = sub.evolves_to[0].species.name;
        }
      }
    }

    if (evolvesTo) {
      const evoPokemonResponse = await fetch(`https://pokeapi.co/api/v2/pokemon/${evolvesTo}`);
      const evoPokemonData = await evoPokemonResponse.json();

      const evoTypes = getTypes(evoPokemonData);
      const evoBst = getBst(evoPokemonData);
      const bstDiff = evoBst - currentBst;

      resultDiv.innerHTML = `
        <h2>Yes, you should evolve ${data.name.toUpperCase()}!</h2>
        <p><strong>Stat Gain:</strong> +${bstDiff} Base Stat Total</p>
        <div style="display:flex; gap: 30px; align-items:center; justify-content:center; margin-top: 15px;">
          <div>
            <h3>${data.name.toUpperCase()}</h3>
            <img src="${data.sprites.front_default}" alt="${data.name}" style="width:120px;">
            <p><strong>Type:</strong> ${currentTypes}</p>
            <p><strong>Base Stat Total:</strong> ${currentBst}</p>
          </div>
          <h2>➔</h2>
          <div>
            <h3>${evoPokemonData.name.toUpperCase()}</h3>
            <img src="${evoPokemonData.sprites.front_default}" alt="${evoPokemonData.name}" style="width:120px;">
            <p><strong>Type:</strong> ${evoTypes}</p>
            <p><strong>Base Stat Total:</strong> ${evoBst}</p>
          </div>
        </div>
      `;
    } else {
      resultDiv.innerHTML = `
        <h2>No / Fully Evolved</h2>
        <p><strong>${data.name.toUpperCase()}</strong> does not evolve further.</p>
        <img src="${data.sprites.front_default}" alt="${data.name}" style="width:120px;">
        <p><strong>Type:</strong> ${currentTypes}</p>
        <p><strong>Base Stat Total:</strong> ${currentBst}</p>
      `;
    }
  } catch (err) {
    resultDiv.innerHTML = `<p style="color:red;">Error: ${err.message}</p>`;
  }
}