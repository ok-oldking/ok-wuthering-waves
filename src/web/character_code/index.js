const STYLE = `
.character-code-page { height: calc(100vh - 66px); min-height: 540px; display: grid; grid-template-columns: minmax(190px, 250px) minmax(0, 1fr); gap: 12px; color: inherit; }
.character-code-page * { box-sizing: border-box; }
.character-code-sidebar, .character-code-workspace { min-height: 0; border: 1px solid var(--stroke); border-radius: 8px; background: var(--card-bg); }
.character-code-sidebar { display: flex; flex-direction: column; padding: 10px; }
.character-code-title { margin: 0 0 8px; font-size: .86rem; font-weight: 600; }
.character-code-list { display: flex; min-height: 0; flex: 1; flex-direction: column; gap: 2px; overflow: auto; }
.character-code-list button { min-height: 34px; padding: 5px 9px; border: 0; border-radius: 5px; background: transparent; text-align: left; cursor: pointer; font-size: .74rem; }
.character-code-list button:hover { background: var(--card-hover); }
.character-code-list button.active { background: var(--selected); color: var(--accent); }
.character-code-list .custom-marker { display: inline-block; width: 13px; color: var(--accent); }
.character-code-workspace { display: grid; grid-template-rows: auto minmax(0, 1fr) auto; padding: 10px; }
.character-code-toolbar, .character-code-footer { display: flex; align-items: center; gap: 8px; }
.character-code-toolbar { min-height: 42px; padding-bottom: 8px; flex-wrap: wrap; }
.character-code-mode { display: flex; align-items: center; gap: 10px; margin-right: auto; font-size: .72rem; }
.character-code-mode label { display: flex; align-items: center; gap: 4px; cursor: pointer; }
.character-code-portrait { display: grid; flex: 0 0 52px; width: 52px; height: 52px; place-items: center; overflow: hidden; }
.character-code-portrait img { display: block; max-width: 48px; max-height: 48px; object-fit: contain; }
.character-code-page button { min-height: 30px; padding: 4px 10px; border: 1px solid var(--stroke); border-radius: 5px; background: var(--card-bg); cursor: pointer; font-size: .7rem; }
.character-code-page button:hover:not(:disabled) { background: var(--card-hover); }
.character-code-page button.primary { border-color: var(--accent); background: var(--accent); color: #102a35; }
.character-code-page button:disabled { opacity: .5; cursor: default; }
.character-code-editor { position: relative; min-height: 0; overflow: hidden; border: 1px solid var(--stroke); border-radius: 6px; background: rgba(0, 0, 0, .16); }
.character-code-editor textarea { width: 100%; height: 100%; resize: none; border: 0; outline: 0; padding: 10px 12px; background: transparent; color: inherit; font: 13px/1.55 Consolas, 'Cascadia Mono', monospace; tab-size: 4; white-space: pre; overflow: auto; }
.character-code-editor textarea[readonly] { color: var(--text-muted); }
.character-code-footer { min-height: 42px; padding-top: 8px; }
.character-code-status { min-width: 0; flex: 1; color: var(--text-muted); font-size: .68rem; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.character-code-status.dirty { color: #f5c36b; }
.character-code-loading { display: grid; place-items: center; height: 100%; color: var(--text-muted); }
@media (max-width: 760px) { .character-code-page { height: auto; grid-template-columns: 1fr; } .character-code-sidebar { max-height: 220px; } .character-code-workspace { min-height: 620px; } }
`;

function html(value) {
  return String(value ?? "").replace(/[&<>\"]/g, (character) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '\"': "&quot;"
  })[character]);
}

export function mount(container, context) {
  const state = {
    characters: [],
    current: null,
    mode: "builtin",
    code: "",
    cleanCode: "",
    busy: false,
    destroyed: false
  };

  container.innerHTML = `<style>${STYLE}</style><div class="character-code-loading">${html(context.t("Loading"))}</div>`;

  const dirty = () => state.mode === "custom" && state.code !== state.cleanCode;
  const setDirty = () => context.setDirty(dirty());
  const confirmDiscard = () => !dirty() || window.confirm(context.t("Discard unsaved character code changes?"));

  async function loadCharacter(className) {
    if (!confirmDiscard()) return false;
    state.busy = true;
    render();
    try {
      const result = await context.query("character", { class_name: className });
      applyCharacter(result);
      return true;
    } catch (error) {
      context.notify(error.message || String(error), "error");
      return false;
    } finally {
      state.busy = false;
      render();
    }
  }

  function applyCharacter(result) {
    state.current = result;
    state.mode = result.use_custom ? "custom" : "builtin";
    state.code = result.code;
    state.cleanCode = result.code;
    const item = state.characters.find((candidate) => candidate.class_name === result.class_name);
    if (item) {
      item.has_custom = result.has_custom;
      item.use_custom = result.use_custom;
    }
    setDirty();
  }

  async function refreshCharacters(selectedClass) {
    state.characters = await context.query("characters");
    const selected = state.characters.find((item) => item.class_name === selectedClass) || state.characters[0];
    if (selected) {
      const result = await context.query("character", { class_name: selected.class_name });
      applyCharacter(result);
    }
  }

  async function setMode(mode) {
    if (!state.current || mode === state.mode) return;
    if (mode === "builtin" && !confirmDiscard()) {
      render();
      return;
    }
    if (mode === "custom" && !state.current.has_custom) {
      state.mode = "custom";
      state.code = state.current.builtin_code;
      state.cleanCode = state.current.builtin_code;
      setDirty();
      render();
      return;
    }
    state.busy = true;
    render();
    try {
      const result = await context.action("mode", {
        class_name: state.current.class_name,
        use_custom: mode === "custom"
      });
      applyCharacter(result);
    } catch (error) {
      context.notify(error.message || String(error), "error");
    } finally {
      state.busy = false;
      render();
    }
  }

  async function save() {
    if (!state.current || state.mode !== "custom") return false;
    state.busy = true;
    render();
    try {
      const result = await context.action("save", {
        class_name: state.current.class_name,
        code: state.code
      });
      applyCharacter(result);
      await refreshCharacters(result.class_name);
      context.notify(context.t(result.message), "success");
      return true;
    } catch (error) {
      context.notify(error.message || String(error), "error");
      return false;
    } finally {
      state.busy = false;
      render();
    }
  }

  async function reset() {
    if (!state.current || !window.confirm(context.t("Reset this character to built in code and remove the custom code?"))) return;
    state.busy = true;
    render();
    try {
      const result = await context.action("reset", { class_name: state.current.class_name });
      applyCharacter(result);
      await refreshCharacters(result.class_name);
      context.notify(context.t(result.message), "success");
    } catch (error) {
      context.notify(error.message || String(error), "error");
    } finally {
      state.busy = false;
      render();
    }
  }

  async function copyAskAi() {
    if (!state.current) return;
    const className = state.current.class_name;
    const template = `\`\`\`python\n${state.code}\n\`\`\`\n\n${context.t("I want to implement:")}\n\n${context.t("Please modify the full {class_name} character automation code above.", { class_name: className })}\n\n${context.t("Return only the complete modified Python code for the whole file, not a patch and not an explanation.")}\n${context.t("Keep the class name as {class_name}. Preserve imports that are still needed.", { class_name: className })}\n\n${context.t("Use this BaseChar reference while reasoning about helper methods, task APIs, state, switching, cooldowns, and combat flow:")}\n${state.current.base_char_url}\n`;
    try {
      await navigator.clipboard.writeText(template);
      context.notify(context.t("Ask AI template copied. Paste it into an AI chatbot."), "success");
    } catch (error) {
      context.notify(error.message || String(error), "error");
    }
  }

  function showHowTo() {
    window.alert(context.t("Choose Use custom to edit a character's Python code. Use built-in mode to read and select the original code.\n\nAsk AI copies a prompt to the clipboard with the full current code at the top. Paste it into an AI chatbot, describe the change after 'I want to implement:', and ask it to return the full modified code.\n\nPaste the returned code back into this editor, review it, then click Save to apply changes."));
  }

  function bind() {
    container.querySelectorAll("[data-character]").forEach((button) => {
      button.addEventListener("click", () => void loadCharacter(button.dataset.character));
    });
    container.querySelectorAll("input[name='character-code-mode']").forEach((radio) => {
      radio.addEventListener("change", () => void setMode(radio.value));
    });
    const editor = container.querySelector("textarea");
    editor?.addEventListener("input", () => {
      state.code = editor.value;
      setDirty();
      updateStatus();
    });
    editor?.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "s") {
        event.preventDefault();
        void save();
      }
      if (event.key === "Tab" && !editor.readOnly) {
        event.preventDefault();
        const start = editor.selectionStart;
        const end = editor.selectionEnd;
        editor.setRangeText("    ", start, end, "end");
        state.code = editor.value;
        setDirty();
        updateStatus();
      }
    });
    container.querySelector("[data-action='save']")?.addEventListener("click", () => void save());
    container.querySelector("[data-action='reset']")?.addEventListener("click", () => void reset());
    container.querySelector("[data-action='ask-ai']")?.addEventListener("click", () => void copyAskAi());
    container.querySelector("[data-action='how-to']")?.addEventListener("click", showHowTo);
    container.querySelector("[data-action='contribute']")?.addEventListener("click", () => {
      if (state.current) window.open(state.current.contribute_url, "_blank", "noopener");
    });
  }

  function updateStatus() {
    const status = container.querySelector(".character-code-status");
    if (!status) return;
    status.classList.toggle("dirty", dirty());
    status.textContent = dirty()
      ? context.t("Unsaved changes")
      : state.mode === "custom" && state.current?.has_custom
        ? context.t("Custom code saved")
        : state.current?.has_custom
          ? context.t("Using built in code")
          : "";
  }

  function render() {
    if (state.destroyed) return;
    if (!state.current) {
      container.innerHTML = `<style>${STYLE}</style><div class="character-code-loading">${html(context.t("Loading"))}</div>`;
      return;
    }
    const currentClass = state.current.class_name;
    container.innerHTML = `<style>${STYLE}</style>
      <section class="character-code-page" aria-label="${html(context.t("Character Code"))}">
        <aside class="character-code-sidebar">
          <h2 class="character-code-title">${html(context.t("Characters"))}</h2>
          <div class="character-code-list">${state.characters.map((item) => `
            <button type="button" data-character="${html(item.class_name)}" class="${item.class_name === currentClass ? "active" : ""}">
              <span class="custom-marker">${item.has_custom ? "*" : ""}</span>${html(context.t(item.display_name))}
            </button>`).join("")}
          </div>
        </aside>
        <div class="character-code-workspace">
          <div class="character-code-toolbar">
            <div class="character-code-portrait">${state.current.image_data_url ? `<img src="${html(state.current.image_data_url)}" alt="${html(context.t(state.current.display_name))}">` : ""}</div>
            <div class="character-code-mode">
              <label><input type="radio" name="character-code-mode" value="builtin" ${state.mode === "builtin" ? "checked" : ""} ${state.busy ? "disabled" : ""}>${html(context.t("Use built in"))}</label>
              <label><input type="radio" name="character-code-mode" value="custom" ${state.mode === "custom" ? "checked" : ""} ${state.busy ? "disabled" : ""}>${html(context.t("Use custom"))}</label>
            </div>
            <button type="button" data-action="ask-ai" ${state.busy ? "disabled" : ""}>${html(context.t("Ask AI"))}</button>
            <button type="button" data-action="how-to">${html(context.t("How To"))}</button>
            <button type="button" data-action="contribute">${html(context.t("Contribute Code"))}</button>
          </div>
          <div class="character-code-editor"><textarea spellcheck="false" ${state.mode === "builtin" ? "readonly" : ""}>${html(state.code)}</textarea></div>
          <div class="character-code-footer">
            <span class="character-code-status"></span>
            ${state.mode === "custom" ? `<button type="button" data-action="reset" ${state.busy ? "disabled" : ""}>${html(context.t("Reset"))}</button><button type="button" class="primary" data-action="save" ${state.busy ? "disabled" : ""}>${html(context.t("Save"))}</button>` : ""}
          </div>
        </div>
      </section>`;
    bind();
    updateStatus();
  }

  context.registerSave(save);
  const unsubscribe = context.subscribe((event) => {
    if (event.name === "character-changed" && event.payload?.class_name === state.current?.class_name && !dirty()) {
      applyCharacter(event.payload);
      render();
    }
  });

  void refreshCharacters().then(render).catch((error) => {
    context.notify(error.message || String(error), "error");
    container.innerHTML = `<style>${STYLE}</style><div class="character-code-loading">${html(error.message || error)}</div>`;
  });

  return () => {
    state.destroyed = true;
    unsubscribe();
    context.registerSave(null);
    context.setDirty(false);
  };
}
