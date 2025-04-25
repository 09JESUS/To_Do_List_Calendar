// Toggle the modal for contact form
document.querySelector('.contact-section a').addEventListener('click', function() {
    document.getElementById('contactModal').style.display = 'block';
});

// Close the modal when the close button is clicked
document.querySelector('.close-btn').addEventListener('click', function() {
    document.getElementById('contactModal').style.display = 'none';
});

// Close the modal if clicked outside of the modal content
window.onclick = function(event) {
    if (event.target == document.getElementById('contactModal')) {
        document.getElementById('contactModal').style.display = 'none';
    }
};
