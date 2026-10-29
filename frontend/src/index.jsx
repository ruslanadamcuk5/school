import React from "react";
import { createRoot } from "react-dom/client";
import NotificationsBell from "./NotificationsBell.jsx";
import NotificationCenter from "./NotificationCenter.jsx";
import LibraryFeed from "./LibraryFeed.jsx";

const roots = new Map();

function mount(selector, Component, getProps) {
  document.querySelectorAll(selector).forEach((node) => {
    if (roots.has(node)) return;
    const root = createRoot(node);
    roots.set(node, root);
    root.render(<Component {...(getProps ? getProps(node) : {})} />);
  });
  document.documentElement.classList.add("react-ready");
}

function boot() {
  mount("[data-react-bell]", NotificationsBell, (node) => ({
    feedUrl: node.getAttribute("data-feed") || "/notifications/feed",
  }));
  mount("[data-react-notifications]", NotificationCenter);
  mount("[data-react-library-feed]", LibraryFeed);
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot);
} else {
  boot();
}
