workspace "Test System" "A minimal workspace for regression testing" {

    model {
        user = person "User" "A user of the system"
        system = softwareSystem "Test System" "The system under test" {
            webapp = container "Web App" "Delivers web content" "React"
            api = container "API" "Handles requests" "Node.js" {
                authController = component "Auth Controller" "Handles login" "Express"
            }
            db = container "Database" "Stores data" "PostgreSQL"
        }

        user -> webapp "Uses" "HTTPS"
        webapp -> api "Calls" "JSON/HTTPS"
        api -> db "Reads/Writes" "SQL/TLS"
    }

}
