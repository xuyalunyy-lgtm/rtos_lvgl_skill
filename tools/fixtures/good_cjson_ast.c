typedef struct cJSON cJSON;
cJSON *cJSON_Parse(const char *text);
void cJSON_Delete(cJSON *item);
int cJSON_GetObjectItem(const cJSON *item, const char *name);

int parse_with_cleanup(const char *text)
{
    int result = -1;
    cJSON *root = cJSON_Parse(text);
    if (root == 0)
        goto cleanup;
    if (cJSON_GetObjectItem(root, "id") == 0)
        goto cleanup;
    result = 0;
cleanup:
    cJSON_Delete(root);
    return result;
}
