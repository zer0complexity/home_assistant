function formatTimestamp(tsStr) {
  if (!tsStr || typeof tsStr !== "string") {
    return "";
  }
  const match = tsStr.match(/(\d{4})(\d{2})(\d{2})(\d{2})(\d{2})(\d{2})/);
  if (!match) {
    return "";
  }
  const [, y, m, d, hh, mm, ss] = match;
  const date = new Date(parseInt(y, 10), parseInt(m, 10) - 1, parseInt(d, 10), parseInt(hh, 10), parseInt(mm, 10), parseInt(ss, 10));
  if (isNaN(date.getTime())) {
    return "";
  }
  try {
    return date.toLocaleString(undefined, { dateStyle: "long", timeStyle: "medium" });
  } catch (e) {
    return date.toLocaleString();
  }
}

class VideoEventCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: "custom:video-event-card",
      image: "media-source://media_source/local/reolink_mirror/example.jpg",
      video: "media-source://media_source/local/reolink_mirror/example.mp4",
    };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }

    this.config = {
      image: "",
      video: "",
      ...config,
    };

    this.render();
    this.resolveMedia();
  }

  set hass(hass) {
    this._hass = hass;
    this.resolveMedia();
  }

  getCardSize() {
    return 3;
  }

  connectedCallback() {
    if (this.config) {
      this.render();
    }
  }

  disconnectedCallback() {
    this.closePlayer();
  }

  render() {
    if (!this.config) {
      return;
    }

    const ts =
      this.config.timestamp ||
      (this.config.image || "").match(/_(\d{14})\./)?.[1] ||
      (this.config.video || "").match(/_(\d{14})\./)?.[1];
    const cardTitle = formatTimestamp(ts);
    const headerAttr = cardTitle ? ` header="${cardTitle}"` : "";

    this.innerHTML = `
      <ha-card${headerAttr}>
        <button class="thumbnail" type="button" aria-label="Play event video">
          <img alt="Event video thumbnail">
          <span class="play" aria-hidden="true">&#9658;</span>
          <span class="status">Loading event...</span>
        </button>
      </ha-card>
      <dialog aria-label="Event video player">
        <div class="player-header">
          <button class="close" type="button" aria-label="Close video player">&times;</button>
        </div>
        <video controls playsinline></video>
      </dialog>
    `;

    this.appendStyles();
    this.querySelector(".thumbnail").addEventListener("click", () => this.openPlayer());
    this.querySelector(".close").addEventListener("click", () => this.closePlayer());
    this.querySelector("dialog").addEventListener("click", (event) => {
      if (event.target === event.currentTarget) {
        this.closePlayer();
      }
    });
    this.querySelector("dialog").addEventListener("close", () => this.stopPlayer());
  }

  async resolveMedia() {
    if (!this.config || !this._hass) {
      return;
    }

    const resolveId = (this._resolveId || 0) + 1;
    this._resolveId = resolveId;

    try {
      const [image, video] = await Promise.all([
        this._hass.callWS({
          type: "media_source/resolve_media",
          media_content_id: this.config.image,
        }),
        this._hass.callWS({
          type: "media_source/resolve_media",
          media_content_id: this.config.video,
        }),
      ]);

      if (resolveId !== this._resolveId) {
        return;
      }

      this._imageUrl = image.url;
      this._videoUrl = video.url;
      const thumbnail = this.querySelector("img");
      const status = this.querySelector(".status");
      thumbnail.src = this._imageUrl;
      status.hidden = true;
    } catch (error) {
      if (resolveId !== this._resolveId) {
        return;
      }

      this._imageUrl = undefined;
      this._videoUrl = undefined;
      this.querySelector(".status").textContent = "Event media is unavailable";
      console.error("Unable to resolve Video Event Card media", error);
    }
  }

  appendStyles() {
    if (this.querySelector("style")) {
      return;
    }

    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      .thumbnail { display: block; position: relative; width: 100%; margin: 0; padding: 0; border: 0; background: #111; cursor: pointer; overflow: hidden; }
      .thumbnail:focus-visible { outline: 3px solid var(--primary-color); outline-offset: -3px; }
      img { display: block; width: 100%; height: auto; }
      .play { position: absolute; top: 50%; left: 50%; display: grid; width: 52px; height: 52px; place-items: center; border-radius: 50%; background: rgb(0 0 0 / 70%); color: #fff; font-size: 24px; transform: translate(-50%, -50%); }
      .status { position: absolute; inset: auto 0 12px; color: #fff; font-size: 14px; }
      dialog { width: calc(100vw - 32px); max-width: calc(100vw - 32px); margin: auto; padding: 0; border: 0; background: #000; color: #fff; }
      dialog::backdrop { background: rgb(0 0 0 / 65%); }
      .player-header { display: flex; justify-content: flex-end; min-height: 40px; }
      .close { width: 40px; height: 40px; border: 0; background: transparent; color: #fff; font-size: 32px; line-height: 1; cursor: pointer; }
      video { display: block; width: 100%; height: auto; max-height: calc(100vh - 88px); }
    `;
    this.append(style);
  }

  openPlayer() {
    if (!this._videoUrl) {
      return;
    }

    const dialog = this.querySelector("dialog");
    const video = this.querySelector("video");
    video.src = this._videoUrl;
    dialog.showModal();
    video.play().catch(() => {});
  }

  closePlayer() {
    const dialog = this.querySelector("dialog");
    if (dialog && dialog.open) {
      dialog.close();
    }
    this.stopPlayer();
  }

  stopPlayer() {
    const video = this.querySelector("video");
    if (video) {
      video.pause();
      video.removeAttribute("src");
      video.load();
    }
  }
}

class CameraEventsCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: "custom:camera-events-card",
      camera_id: 0,
      media_dir: "reolink_mirror",
    };
  }

  setConfig(config) {
    if (!config) {
      throw new Error("Invalid configuration");
    }

    const camIdRaw = config.camera_id !== undefined ? config.camera_id : 0;
    const camId = typeof camIdRaw === "number" ? camIdRaw : parseInt(camIdRaw, 10);
    const validCamId = !isNaN(camId) && camId >= 0 ? camId : 0;

    const mediaDir = config.media_dir && typeof config.media_dir === "string" ? config.media_dir.trim() : "reolink_mirror";

    this.config = {
      ...config,
      camera_id: validCamId,
      media_dir: mediaDir,
    };

    this.render();
    this.loadEvents();
  }

  set hass(hass) {
    this._hass = hass;

    const childCards = this.querySelectorAll("video-event-card");
    childCards.forEach((card) => {
      card.hass = hass;
    });

    if (!this._loadedEvents) {
      this.loadEvents();
    }
  }

  getCardSize() {
    return 4;
  }

  connectedCallback() {
    if (this.config) {
      this.render();
      if (this._hass && !this._loadedEvents) {
        this.loadEvents();
      }
    }
  }

  render() {
    if (!this.config) {
      return;
    }

    const cameraName = this.config.camera_name;
    const headerTitle = cameraName ? `${cameraName} Events` : `Camera ${this.config.camera_id} Events`;

    const existingCard = this.querySelector("ha-card");
    if (existingCard) {
      existingCard.setAttribute("header", headerTitle);
      return;
    }

    this.innerHTML = `
      <ha-card header="${headerTitle}">
        <div class="events-container">
          <div class="status">Loading events...</div>
        </div>
      </ha-card>
    `;
    this.appendStyles();
  }

  appendStyles() {
    if (this.querySelector("style")) {
      return;
    }

    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      ha-card { padding: 16px; }
      .events-grid { display: grid; grid-template-columns: 1fr; gap: 16px; }
      .status, .empty, .error { text-align: center; color: var(--secondary-text-color, #888); padding: 16px 0; }
    `;
    this.append(style);
  }

  async loadEvents() {
    if (!this.config || !this._hass) {
      return;
    }

    const loadId = (this._loadId || 0) + 1;
    this._loadId = loadId;

    const container = this.querySelector(".events-container");

    try {
      let cleanDir = this.config.media_dir.trim().replace(/^\/+|\/+$/g, "");
      if (cleanDir.startsWith("media-source://media_source/")) {
        cleanDir = cleanDir.replace("media-source://media_source/", "");
      }
      if (cleanDir.startsWith("local/")) {
        cleanDir = cleanDir.substring(6);
      }

      const rootMediaId = `media-source://media_source/local/${cleanDir}`;
      const items = await this._fetchMediaFiles(rootMediaId);

      if (loadId !== this._loadId) {
        return;
      }

      const dd = String(this.config.camera_id).padStart(2, "0");
      const filenameRegex = new RegExp(`NVR_${dd}_(\\d{14})\\.(jpg|jpeg|mp4|mkv|avi|mov)$`, "i");

      const eventsMap = new Map();

      for (const item of items) {
        const title = item.title || item.media_content_id.split("/").pop() || "";
        const match = title.match(filenameRegex);
        if (!match) {
          continue;
        }

        const timestamp = match[1];
        const ext = match[2].toLowerCase();

        if (!eventsMap.has(timestamp)) {
          eventsMap.set(timestamp, { timestamp });
        }

        const event = eventsMap.get(timestamp);
        if (ext === "jpg" || ext === "jpeg") {
          event.imageMediaId = item.media_content_id;
        } else {
          event.videoMediaId = item.media_content_id;
        }
      }

      const validEvents = Array.from(eventsMap.values())
        .filter((e) => e.imageMediaId && e.videoMediaId)
        .sort((a, b) => b.timestamp.localeCompare(a.timestamp));

      if (!container) {
        return;
      }

      const cameraName = this.config.camera_name;
      const displayName = cameraName || `camera ${this.config.camera_id}`;

      if (validEvents.length === 0) {
        container.innerHTML = `<div class="empty">No events found for ${displayName}</div>`;
        this._loadedEvents = true;
        return;
      }

      const grid = document.createElement("div");
      grid.className = "events-grid";

      for (const event of validEvents) {
        const card = document.createElement("video-event-card");
        card.setConfig({
          image: event.imageMediaId,
          video: event.videoMediaId,
          timestamp: event.timestamp,
        });
        if (this._hass) {
          card.hass = this._hass;
        }
        grid.appendChild(card);
      }

      container.innerHTML = "";
      container.appendChild(grid);
      this._loadedEvents = true;
    } catch (err) {
      if (loadId !== this._loadId) {
        return;
      }
      console.error("Failed to load camera events", err);
      const cameraName = this.config.camera_name;
      const displayName = cameraName || `camera ${this.config.camera_id}`;
      if (container) {
        container.innerHTML = `<div class="error">Failed to load events for ${displayName}</div>`;
      }
    }
  }

  async _fetchMediaFiles(mediaContentId) {
    const results = [];
    const queue = [mediaContentId];
    const visited = new Set();

    while (queue.length > 0) {
      const currentId = queue.shift();
      if (visited.has(currentId)) {
        continue;
      }
      visited.add(currentId);

      try {
        const res = await this._hass.callWS({
          type: "media_source/browse_media",
          media_content_id: currentId,
        });

        if (res.children) {
          for (const child of res.children) {
            if (child.can_expand) {
              queue.push(child.media_content_id);
            } else {
              results.push(child);
            }
          }
        }
      } catch (e) {
        console.warn(`Could not browse media location: ${currentId}`, e);
      }
    }

    return results;
  }
}

customElements.define("video-event-card", VideoEventCard);
customElements.define("camera-events-card", CameraEventsCard);

window.customCards = window.customCards || [];
window.customCards.push(
  {
    type: "video-event-card",
    name: "Video Event Card",
    description: "Shows an event thumbnail and opens its associated video.",
  },
  {
    type: "camera-events-card",
    name: "Camera Events Card",
    description: "Displays a 1-column grid of video event cards for a specific camera ID.",
  }
);
