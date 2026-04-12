function getCsrfToken() {
    return document.querySelector('meta[name="csrf-token"]')?.getAttribute("content") || "";
}

function resultMessage(msg) {
    var el = document.getElementById("result-message");
    if (el) el.innerHTML = msg;
}

window.paypal
    .Buttons({
        style: {
            shape: "pill",
            layout: "vertical",
            color: "gold",
            label: "paypal",
        },

        async createOrder() {
            try {
                const response = await fetch("/api/orders", {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        "X-CSRFToken": getCsrfToken(),
                    },
                    body: JSON.stringify({
                        product_id: PRODUCT_ID,
                    }),
                });

                const orderData = await response.json();

                if (orderData.id) {
                    return orderData.id;
                }
                const errorDetail = orderData?.details?.[0];
                const errorMessage = errorDetail
                    ? `${errorDetail.issue} ${errorDetail.description} (${orderData.debug_id})`
                    : JSON.stringify(orderData);

                throw new Error(errorMessage);
            } catch (error) {
                console.error(error);
                resultMessage("Could not initiate PayPal Checkout. Please try again.");
            }
        } ,

        async onApprove(data, actions) {
            try {
                const response = await fetch(
                    `/api/orders/${data.orderID}/capture`,
                    {
                        method: "POST",
                        headers: {
                            "Content-Type": "application/json",
                            "X-CSRFToken": getCsrfToken(),
                        },
                    }
                );

                const orderData = await response.json();

                const errorDetail = orderData?.details?.[0];

                if (errorDetail?.issue === "INSTRUMENT_DECLINED") {
                    return actions.restart();
                } else if (errorDetail) {
                    throw new Error(
                        `${errorDetail.description} (${orderData.debug_id})`
                    );
                } else if (!orderData.purchase_units) {
                    throw new Error(JSON.stringify(orderData));
                } else {
                    const transaction =
                        orderData?.purchase_units?.[0]?.payments
                            ?.captures?.[0] ||
                        orderData?.purchase_units?.[0]?.payments
                            ?.authorizations?.[0];
                    resultMessage(
                        `Transaction ${transaction.status}: ${transaction.id}. Currency credited!`
                    );
                }
            } catch (error) {
                console.error(error);
                resultMessage(
                    "Sorry, your transaction could not be processed. Please try again."
                );
            }
        } ,
    })
    .render("#paypal-button-container");
