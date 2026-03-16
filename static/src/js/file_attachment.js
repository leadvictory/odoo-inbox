window.onload = function () {

    const fileInputs = document.querySelectorAll(".compose_attach_file");

    fileInputs.forEach(input => {

        let storedFiles = [];

        input.addEventListener("change", function (event) {

            console.log("Files selected");

            const previewContainer = input.parentNode.nextElementSibling;
            const files = Array.from(event.target.files);

            console.log("Raw files from input:", files);

            files.forEach(file => {

                console.log("Processing file:", file.name);

                // prevent duplicates
                if (storedFiles.find(f => f.name === file.name)) {
                    console.log("Duplicate skipped:", file.name);
                    return;
                }

                storedFiles.push(file);

                console.log("Stored files:", storedFiles);

                const reader = new FileReader();

                reader.onload = function (e) {

                    const div = document.createElement("div");

                    let icon = "/odoo_inbox/static/src/img/zip.png";

                    if (file.type.startsWith("image")) {
                        icon = e.target.result;
                    }
                    else if (file.type === "application/pdf") {
                        icon = "/odoo_inbox/static/src/img/pdf.png";
                    }
                    else if (file.type.includes("excel")) {
                        icon = "/odoo_inbox/static/src/img/excel.png";
                    }

                    div.innerHTML =
                        "<span class='fa fa-times-circle remove-file'></span>" +
                        "<img class='thumbnail' src='" + icon + "' title='" + file.name + "'/>";

                    previewContainer.appendChild(div);

                    div.querySelector(".remove-file").onclick = function () {

                        console.log("Removing file:", file.name);

                        storedFiles = storedFiles.filter(f => f.name !== file.name);

                        const dt = new DataTransfer();
                        storedFiles.forEach(f => dt.items.add(f));

                        input.files = dt.files;

                        console.log("Remaining files:", storedFiles);

                        div.remove();
                    };

                };

                reader.readAsDataURL(file);

            });

            // update input file list
            const dt = new DataTransfer();
            storedFiles.forEach(f => dt.items.add(f));
            input.files = dt.files;

            console.log("Final files inside input:", input.files);

        });

    });

};