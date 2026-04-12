// Control Room JS
// HTMX handles most interactions. This file is for extra behavior.

window.controlRoom = {
    openDrawer() {
        window.dispatchEvent(new CustomEvent('control-room:open-drawer'));
    },
    closeDrawer() {
        window.dispatchEvent(new CustomEvent('control-room:close-drawer'));
    }
};

// After HTMX swaps, reinitialize any Alpine components
document.addEventListener('htmx:afterSwap', function(event) {
    // Alpine auto-initializes via x-data, nothing extra needed
    if (event.target && event.target.id === 'drawer-content') {
        window.controlRoom.openDrawer();
    }
});

// Global keyboard shortcuts
document.addEventListener('keydown', function(event) {
    // Escape closes the detail drawer
    if (event.key === 'Escape') {
        window.controlRoom.closeDrawer();
    }
});
