class VideoEventCard extends HTMLElement {
  static getStubConfig() {
    return {
      type: "custom:video-event-card",
      image: "/media/local/reolink_mirror/example.jpg",
      video: "/media/local/reolink_mirror/example.mp4",
    };
  }

  setConfig(config) {
    if (!config.image || typeof config.image !== "string") {
      throw new Error("Video Event Card requires an image URL.");
    }
    if (!config.video || typeof config.video !== "string") {
      throw new Error("Video Event Card requires a video URL.");
    }

    this.config = config;
    this.render();
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

    this.innerHTML = `
      <ha-card>
        <button class="thumbnail" type="button" aria-label="Play event video">
          <img src="${this.config.image}" alt="Event video thumbnail">
          <span class="play" aria-hidden="true">&#9658;</span>
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

  appendStyles() {
    if (this.querySelector("style")) {
      return;
    }

    const style = document.createElement("style");
    style.textContent = `
      :host { display: block; }
      .thumbnail { display: block; position: relative; width: 100%; margin: 0; padding: 0; border: 0; background: #111; cursor: pointer; overflow: hidden; }
      .thumbnail:focus-visible { outline: 3px solid var(--primary-color); outline-offset: -3px; }
      img { display: block; width: 100%; height: auto; max-height: 360px; object-fit: cover; }
      .play { position: absolute; top: 50%; left: 50%; display: grid; width: 52px; height: 52px; place-items: center; border-radius: 50%; background: rgb(0 0 0 / 70%); color: #fff; font-size: 24px; transform: translate(-50%, -50%); }
      dialog { width: min(960px, calc(100vw - 32px)); margin: auto; padding: 0; border: 0; background: #000; color: #fff; }
      dialog::backdrop { background: rgb(0 0 0 / 65%); }
      .player-header { display: flex; justify-content: flex-end; min-height: 40px; }
      .close { width: 40px; height: 40px; border: 0; background: transparent; color: #fff; font-size: 32px; line-height: 1; cursor: pointer; }
      video { display: block; width: 100%; max-height: calc(100vh - 88px); }
    `;
    this.append(style);
  }

  openPlayer() {
    const dialog = this.querySelector("dialog");
    const video = this.querySelector("video");
    video.src = this.config.video;
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

customElements.define("video-event-card", VideoEventCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "video-event-card",
  name: "Video Event Card",
  description: "Shows an event thumbnail and opens its associated video.",
});