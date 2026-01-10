const roleButtons = document.querySelectorAll(".role-btn");
const roleInput = document.getElementById("selectedRole");

roleButtons.forEach(btn => {
    btn.addEventListener("click", () => {

        // Remove active class
        roleButtons.forEach(b => b.classList.remove("active"));

        // Add active class
        btn.classList.add("active");

        // Set hidden input value
        roleInput.value = btn.dataset.role;
    });
});

