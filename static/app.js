
document.addEventListener("DOMContentLoaded", () => {
  // V6.4: garante que todos os previews comecem limpos.
  document.querySelectorAll(".aom-avatar-preview").forEach((img) => {
    img.hidden = true;
    img.style.display = "none";
    img.style.visibility = "hidden";
    img.removeAttribute("src");
  });

  document.querySelectorAll(".community-preview-placeholder").forEach((placeholder) => {
    placeholder.style.display = "grid";
  });

  document.querySelectorAll(".lookup-aom").forEach((button) => {
    button.addEventListener("click", async () => {
      const box = button.closest(".lookup-player-box");
      if (!box) return;
      const urlInput = box.querySelector(".aom-url");
      const nickInput = box.querySelector(".aom-nick");
      const eloInput = box.querySelector(".aom-elo");
      const status = box.querySelector(".lookup-status");
      const form = button.closest("form");
      const mode = (form && form.dataset.eloMode) || "1v1";
      if (!urlInput || !urlInput.value.trim()) {
        status.className = "lookup-status error";
        status.textContent = "Cole primeiro o link do perfil AoMStats.";
        return;
      }
      button.disabled = true;
      const oldText = button.textContent;
      button.textContent = "BUSCANDO...";
      status.className = "lookup-status";
      status.textContent = "Consultando AoMStats e Steam...";
      try {
        const r = await fetch(`/api/aomstats?mode=${encodeURIComponent(mode)}&url=${encodeURIComponent(urlInput.value.trim())}`);
        const data = await r.json();
        if (!r.ok || !data.ok) throw new Error(data.error || "Falha na consulta");
        if (nickInput && data.nickname) nickInput.value = data.nickname;
        if (eloInput) {
          eloInput.value = (data.elo !== null && data.elo !== undefined) ? data.elo : "";
          eloInput.placeholder = (data.elo !== null && data.elo !== undefined) ? "Elo encontrado" : "SEM ELO";
        }

        // V6.1: prévia visual para o Elo da Comunidade.
        const avatarPreview = box.querySelector(".aom-avatar-preview");
        const avatarPlaceholder = box.querySelector(".community-preview-placeholder");
        const previewName = box.querySelector(".aom-preview-name");
        const previewElo = box.querySelector(".aom-preview-elo");
        if (previewName && data.nickname) previewName.textContent = data.nickname;
        if (previewElo) {
          const normalExtra = data.normal_stats_available
            ? ` • ${data.normal_wins}V/${data.normal_losses}D • Nv.${data.normal_level}`
            : "";
          previewElo.textContent = data.elo !== null && data.elo !== undefined
            ? `${data.elo} ELO${normalExtra}`
            : `SEM ELO${normalExtra}`;
        }
        const normalStatsPreview = box.querySelector(".aom-normal-stats");
        if (normalStatsPreview) {
          normalStatsPreview.textContent = data.normal_stats_available
            ? `${data.normal_wins} vitórias • ${data.normal_losses} derrotas • ${data.normal_win_rate}% • Nível ${data.normal_level} (${data.normal_level_label})`
            : "O AoMStats não retornou contagem de partidas normais para este perfil.";
        }
        if (avatarPreview) {
          // Sempre começa escondido. Só exibe depois que a URL realmente carregar.
          avatarPreview.hidden = true;
          avatarPreview.style.display = "none";
          avatarPreview.style.visibility = "hidden";
          avatarPreview.removeAttribute("src");
          if (avatarPlaceholder) avatarPlaceholder.style.display = "grid";

          if (data.avatar_url) {
            const candidateUrl = data.avatar_url;
            avatarPreview.onload = () => {
              avatarPreview.hidden = false;
              avatarPreview.style.display = "block";
              avatarPreview.style.visibility = "visible";
              if (avatarPlaceholder) avatarPlaceholder.style.display = "none";
            };
            avatarPreview.onerror = () => {
              avatarPreview.hidden = true;
              avatarPreview.style.display = "none";
              avatarPreview.style.visibility = "hidden";
              avatarPreview.removeAttribute("src");
              if (avatarPlaceholder) avatarPlaceholder.style.display = "grid";
            };
            avatarPreview.src = candidateUrl;
          }
        }

        status.className = "lookup-status success";
        status.textContent = data.elo
          ? `✓ ${data.nickname} • Elo ${data.elo} • ${data.normal_wins}V/${data.normal_losses}D em normais`
          : `✓ ${data.nickname} • SEM ELO • Nível ${data.normal_level} • ${data.normal_wins}V/${data.normal_losses}D em normais`;
      } catch (err) {
        status.className = "lookup-status error";
        status.textContent = `${err.message} Você pode preencher Nick e Elo manualmente.`;
      } finally {
        button.disabled = false;
        button.textContent = oldText;
      }
    });
  });



  // V7: uma imagem escolhida no PC substitui visualmente o avatar remoto no preview.
  document.querySelectorAll(".manual-avatar-input").forEach((input) => {
    input.addEventListener("change", () => {
      const file = input.files && input.files[0];
      if (!file) return;
      if (!file.type.startsWith("image/")) return;

      const box = input.closest(".lookup-player-box");
      if (!box) return;
      const preview = box.querySelector(".aom-avatar-preview");
      const placeholder = box.querySelector(".community-preview-placeholder");
      if (!preview) return;

      const reader = new FileReader();
      reader.onload = () => {
        preview.onload = null;
        preview.onerror = null;
        preview.src = reader.result;
        preview.hidden = false;
        preview.style.display = "block";
        preview.style.visibility = "visible";
        if (placeholder) placeholder.style.display = "none";
      };
      reader.readAsDataURL(file);
    });
  });

    // Se uma foto remota falhar, escondemos a imagem quebrada em vez de poluir o layout.
  document.querySelectorAll("img.avatar-img,img.winner-avatar,img.admin-avatar").forEach((img) => {
    img.addEventListener("error", () => { img.style.visibility = "hidden"; });
  });
});


// V5: o formulário de criação pode deixar o limite em branco e usar o padrão do modo.
document.addEventListener("DOMContentLoaded", () => {
  const mode = document.getElementById("mode-key-select");
  if (!mode) return;
  const maxInput = document.querySelector('form[action$="/admin/torneios/criar"] input[name="max_entries"]');
  const defaults = {ffa:12, food_wood_gold:12, "1v1_round_robin":32, "2v2_elimination":16, bo3_1v1:32, bo3_2v2:16, bo3_3v3:12};
  const refresh = () => { if (maxInput && (!maxInput.dataset.touched || maxInput.value === "")) maxInput.value = defaults[mode.value] || 12; };
  if (maxInput) maxInput.addEventListener("input", () => maxInput.dataset.touched = "1");
  mode.addEventListener("change", () => { if (maxInput) { maxInput.dataset.touched = ""; maxInput.value = defaults[mode.value] || 12; } });
  refresh();
});
