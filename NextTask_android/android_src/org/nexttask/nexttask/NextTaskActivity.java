
package org.nexttask.nexttask;

import org.kivy.android.PythonActivity;

import android.content.Intent;
import android.content.ClipData;
import android.database.Cursor;
import android.net.Uri;
import android.os.Bundle;
import android.provider.DocumentsContract;
import android.provider.OpenableColumns;

import java.io.File;
import java.io.InputStream;
import java.io.FileOutputStream;
import java.util.ArrayList;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

import org.json.JSONArray;
import org.json.JSONObject;

public class NextTaskActivity extends PythonActivity {

    private static NextTaskActivity instance;

    private static final int REQUEST_FILES = 4101;
    private static final int REQUEST_FOLDER = 4102;
    private static final int REQUEST_SAVE_FILE = 4103;

    private static String pendingResult = null;
    private static String pendingSavePath = null;

    private static final ExecutorService executor =
            Executors.newSingleThreadExecutor();

    @Override
    protected void onCreate(Bundle savedInstanceState) {
        super.onCreate(savedInstanceState);
        instance = this;
    }

    public static void launchFiles() {
        if (instance == null) return;

        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT);
        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType("*/*");
        intent.putExtra(Intent.EXTRA_ALLOW_MULTIPLE, true);

        intent.addFlags(
            Intent.FLAG_GRANT_READ_URI_PERMISSION |
            Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
        );

        instance.startActivityForResult(intent, REQUEST_FILES);
    }

    public static void launchFolder() {
        if (instance == null) return;

        Intent intent = new Intent(Intent.ACTION_OPEN_DOCUMENT_TREE);

        intent.addFlags(
            Intent.FLAG_GRANT_READ_URI_PERMISSION |
            Intent.FLAG_GRANT_WRITE_URI_PERMISSION |
            Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
        );

        instance.startActivityForResult(intent, REQUEST_FOLDER);
    }

    public static void launchSaveFile(String mimeType) {
        if (instance == null) return;

        Intent intent = new Intent(Intent.ACTION_CREATE_DOCUMENT);

        intent.addCategory(Intent.CATEGORY_OPENABLE);
        intent.setType(mimeType);

        intent.addFlags(
            Intent.FLAG_GRANT_READ_URI_PERMISSION |
            Intent.FLAG_GRANT_WRITE_URI_PERMISSION |
            Intent.FLAG_GRANT_PERSISTABLE_URI_PERMISSION
        );

        instance.startActivityForResult(intent, REQUEST_SAVE_FILE);
    }

    @Override
    protected void onActivityResult(
            int requestCode,
            int resultCode,
            Intent data) {

        super.onActivityResult(requestCode, resultCode, data);

        if (requestCode != REQUEST_FILES &&
            requestCode != REQUEST_FOLDER) {
            return;
        }

        if (resultCode != RESULT_OK || data == null) {
            setResult("{\"ok\":false,\"cancelled\":true}");
            return;
        }

        if (requestCode == REQUEST_SAVE_FILE) {
            if (resultCode != RESULT_OK || data == null) {
                setResult("{\"ok\":false,\"cancelled\":true}");
                return;
            }

            Uri uri = data.getData();

            JSONObject result = new JSONObject();
            result.put("ok", true);
            result.put("url", uri.toString());

            setResult(result.toString());
            return;
        }

        final NextTaskActivity activity = this;
        final Intent resultIntent = data;

        executor.execute(() -> {
            try {
                if (requestCode == REQUEST_FILES) {
                    processFiles(activity, resultIntent);
                } else {
                    processFolder(activity, resultIntent);
                }
            } catch (Exception e) {
                setError(e.toString());
            }
        });
    }

    private static synchronized void setResult(String result) {
        pendingResult = result;
    }

    private static synchronized void setError(String error) {
        try {
            JSONObject obj = new JSONObject();
            obj.put("ok", false);
            obj.put("error", error);
            pendingResult = obj.toString();
        } catch (Exception ignored) {
        }
    }

    public static synchronized boolean hasPendingResult() {
        return pendingResult != null;
    }

    public static synchronized String consumePendingResult() {
        String result = pendingResult;
        pendingResult = null;
        return result;
    }

    public static synchronized void clearPendingResult() {
        pendingResult = null;
    }

    private static File createImportDirectory(
            NextTaskActivity activity,
            String name) {

        File dir = new File(
            activity.getFilesDir(),
            "imports/" + name + "_" + System.currentTimeMillis()
        );

        dir.mkdirs();
        return dir;
    }

    private static String safeName(String name) {
        if (name == null || name.isEmpty()) {
            name = "unnamed";
        }

        return name.replaceAll("[\\\\/:*?\"<>|]", "_");
    }

    private static String getDisplayName(
            NextTaskActivity activity,
            Uri uri) {

        try (Cursor cursor = activity.getContentResolver().query(
                uri,
                null,
                null,
                null,
                null)) {

            if (cursor != null &&
                cursor.moveToFirst()) {

                int index = cursor.getColumnIndex(
                    OpenableColumns.DISPLAY_NAME
                );

                if (index >= 0) {
                    return safeName(cursor.getString(index));
                }
            }
        } catch (Exception ignored) {
        }

        return "unnamed";
    }

    private static File copyFile(
            NextTaskActivity activity,
            Uri uri,
            File destination) throws Exception {

        try (
            InputStream input =
                activity.getContentResolver().openInputStream(uri);

            FileOutputStream output =
                new FileOutputStream(destination)
        ) {
            if (input == null) {
                throw new Exception("Cannot open: " + uri);
            }

            byte[] buffer = new byte[8192];
            int count;

            while ((count = input.read(buffer)) != -1) {
                output.write(buffer, 0, count);
            }
        }

        return destination;
    }

    private static void processFiles(
            NextTaskActivity activity,
            Intent data) throws Exception {

        File outputDir = createImportDirectory(activity, "files");

        ArrayList<Uri> uris = new ArrayList<>();

        ClipData clip = data.getClipData();

        if (clip != null) {
            for (int i = 0; i < clip.getItemCount(); i++) {
                uris.add(clip.getItemAt(i).getUri());
            }
        } else if (data.getData() != null) {
            uris.add(data.getData());
        }

        JSONArray paths = new JSONArray();

        for (Uri uri : uris) {
            String name = getDisplayName(activity, uri);

            File destination = new File(outputDir, name);

            // Avoid overwriting files with identical names.
            int counter = 1;
            while (destination.exists()) {
                destination = new File(
                    outputDir,
                    counter++ + "_" + name
                );
            }

            copyFile(activity, uri, destination);
            paths.put(destination.getAbsolutePath());
        }

        JSONObject result = new JSONObject();
        result.put("ok", true);
        result.put("kind", "files");
        result.put("paths", paths);

        setResult(result.toString());
    }

    private static void processFolder(
            NextTaskActivity activity,
            Intent data) throws Exception {

        Uri treeUri = data.getData();

        int flags = data.getFlags() &
            (Intent.FLAG_GRANT_READ_URI_PERMISSION |
             Intent.FLAG_GRANT_WRITE_URI_PERMISSION);

        try {
            activity.getContentResolver()
                .takePersistableUriPermission(treeUri, flags);
        } catch (Exception ignored) {
        }

        String rootId =
            DocumentsContract.getTreeDocumentId(treeUri);

        Uri rootUri =
            DocumentsContract.buildDocumentUriUsingTree(
                treeUri, rootId
            );

        String rootName = getDisplayName(activity, rootUri);

        File outputDir = createImportDirectory(activity, rootName);

        copyDirectory(activity, treeUri, rootId, outputDir);

        JSONObject result = new JSONObject();
        result.put("ok", true);
        result.put("kind", "folder");
        result.put("path", outputDir.getAbsolutePath());

        setResult(result.toString());
    }

    private static void copyDirectory(
            NextTaskActivity activity,
            Uri treeUri,
            String parentId,
            File destination) throws Exception {

        Uri childrenUri =
            DocumentsContract.buildChildDocumentsUriUsingTree(
                treeUri, parentId
            );

        String[] projection = {
            DocumentsContract.Document.COLUMN_DOCUMENT_ID,
            DocumentsContract.Document.COLUMN_DISPLAY_NAME,
            DocumentsContract.Document.COLUMN_MIME_TYPE
        };

        try (Cursor cursor = activity.getContentResolver().query(
                childrenUri,
                projection,
                null,
                null,
                null)) {

            if (cursor == null) {
                throw new Exception("Cannot list folder contents");
            }

            while (cursor.moveToNext()) {

                String id = cursor.getString(0);
                String name = safeName(cursor.getString(1));
                String mime = cursor.getString(2);

                File child = new File(destination, name);

                Uri childUri =
                    DocumentsContract.buildDocumentUriUsingTree(
                        treeUri, id
                    );

                if (DocumentsContract.Document.MIME_TYPE_DIR.equals(mime)) {

                    child.mkdirs();

                    copyDirectory(
                        activity,
                        treeUri,
                        id,
                        child
                    );

                } else {

                    // Prevent overwriting duplicate filenames.
                    int counter = 1;

                    while (child.exists()) {
                        child = new File(
                            destination,
                            counter++ + "_" + name
                        );
                    }

                    copyFile(activity, childUri, child);
                }
            }
        }
    }
}
