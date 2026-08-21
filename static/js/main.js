// Skill Verse Main JS

// Auto-hide alerts after 4s
document.querySelectorAll('.alert').forEach(el => {
  setTimeout(() => { el.style.opacity = '0'; el.style.transition = 'opacity .5s'; setTimeout(() => el.remove(), 500); }, 4000);
});

// Add enumerate filter support (for Jinja2 enumerate)
// Mobile sidebar toggle
function toggleSidebar() {
  document.querySelector('.sidebar').classList.toggle('open');
}

// Smooth animations on load
document.addEventListener('DOMContentLoaded', () => {
  const cards = document.querySelectorAll('.stat-card, .card, .course-card');
  cards.forEach((card, i) => {
    card.style.opacity = '0';
    card.style.transform = 'translateY(12px)';
    setTimeout(() => {
      card.style.transition = 'opacity .3s, transform .3s';
      card.style.opacity = '1';
      card.style.transform = 'translateY(0)';
    }, i * 40);
  });
});
