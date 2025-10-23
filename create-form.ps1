# Define the API endpoint and your API key
$apiKey = "vf_ItJeay32VNwIv9Te-KO2J5sHa2H2pqpIg8dil4n6foI"
$baseUrl = "http://localhost:8000"

#description for each field in the form -> customer name : name of the customer, rating : rating of the customer
#text llm gets this part. 
# Define the form
$formData = @{
    name = "Customer Survey"
    description = "Quick customer feedback"
    fields = @(
        @{
            name = "customer_name"
            type = "text"
            required = $true
            prompt = "What is your name?"
        },
        @{
            name = "rating"
            type = "number"
            required = $true
            prompt = "Rate us from 1 to 10"
            validation = @{
                min = 1
                max = 10
            }
        }
    )
    ai_prompt = "Hello! Thanks for your feedback."
    callback_url = "https://webhook.site/your-unique-id"
    success_message = "Thank you!"
}

# Convert to JSON
$jsonBody = $formData | ConvertTo-Json -Depth 10

# Make the request
$headers = @{
    "X-API-Key" = $apiKey
    "Content-Type" = "application/json"
}

try {
    $response = Invoke-RestMethod -Uri "$baseUrl/api/forms/" -Method POST -Headers $headers -Body $jsonBody
    
    Write-Host "`n✅ Form Created Successfully!" -ForegroundColor Green
    Write-Host "`nForm ID: $($response.form_id)" -ForegroundColor Cyan
    Write-Host "Magic Link: $($response.magic_link)" -ForegroundColor Yellow
    Write-Host "Webhook Secret: $($response.webhook_secret)" -ForegroundColor Magenta
    Write-Host "`n🎯 Share this link with users: $($response.magic_link)" -ForegroundColor Green
}
catch {
    Write-Host "`n❌ Error:" -ForegroundColor Red
    Write-Host $_.Exception.Message -ForegroundColor Red
}