<?php

// This script is intended to handle requests for files that do not exist
// This may occur because:
// 1) It is a language-free URL and we need to send the user to the most language appropriate version for them
// 2) The page has moved elsewhere and we need to send them to the appropriate page
// 3) The request is for a legacy page that existed on the older Mediawiki based setup, in which case we need to once again send them to the most appropriate page

// Our list of supported languages
$supported_languages = array(
    "en",
);

// List of page redirect rules
// These should always be free of the language code, as this will be automatically added on when formulating the URL to forward the user on to
$redirect_rules = array(
    // Default front page
    "^$" => "index.html",

);

//// SETTINGS END
//// CHANGES SHOULD NOT BE NEEDED TO THE BELOW

// Helper function to determine the most appropriate language for the user
// Parameters:
// $request              The web path that the user is trying to reach
// $browser_languages    The languages accepted by the user browser, in Accept-Language format
// $supported_languages  Array of languages that we support - in ISO language code format
function determine_appropriate_language( $request, $browser_languages, $supported_languages )
{
    // First we start by looking at the request we have received
    // If this contains a language code, then we should be using that as the user has chosen to use that language explicitly
    // We assume that this language is supported
    if( preg_match( '/^([a-z][a-z](_[A-Z][A-Z])?)\//', $request, $result ) ) {
        // Then the user has specified a language - let's use that!
        return $result[1];
    }

    // Now that we know that the URL has not specified a language we can move on to looking at Accept-Language
    // First split the list up by the language separator
    $browser_requested_languages = explode( ",", $browser_languages );

    // Now go through each browser requested language in turn
    foreach( $browser_requested_languages as $language ) {
        // First as this might have a weighting value on it, we need to rip that off
        // Safest way to do this is just to split again by the appropriate separator for that
        $components = explode(";", $language);
        $language = $components[0];

        if( preg_match( '/^zh(-han[ts])?(-[a-z]{2})?$/i', $language, $result, PREG_UNMATCHED_AS_NULL ) ) {
            // Handle Chinese as a special case. Chinese lang tags may carry
            // a `Hant` or `Hans` script subtag, and/or a region subtag.
            // As long as a translation for `zh_HK` isn't available, this
            // matching is sufficient.
            if( strcasecmp($result[1], "-hant") === 0 ) {
                $language = "zh_TW";
            } else if( strcasecmp($result[1], "-hans") === 0 ) {
                $language = "zh_CN";
            } else if( strcasecmp($result[2], "-tw") === 0 || strcasecmp($result[2], "-hk") === 0 || strcasecmp($result[2], "-mo") === 0 ) {
                $language = "zh_TW";
            } else {
                // Note this also matches `zh` without script or region subtag.
                $language = "zh_CN";
            }
        } else {
            // Browsers use dashes to seperate language variants
            // But KDE translation systems use underscores for this so ensure we are consistent here
            $language = str_replace("-", "_", $language);
        }

        // Is this one of our supported languages?
        if( in_array($language, $supported_languages) ) {
            // Then we have a winner!
            return $language;
        }
    }

    // Finally if we found nothing we fallback to English
    return 'en';
}

// Start - Retrieve the values we need to work with here
$requested_url = $_SERVER['REQUEST_URI'];
$requested_languages = $_SERVER["HTTP_ACCEPT_LANGUAGE"];

// Before we can do anything else we need to clean up the URL we have received to remove the leading slash
$requested_url = substr($requested_url, 1);

// Now determine the language we should be sending the user to
$language = determine_appropriate_language( $requested_url, $requested_languages, $supported_languages );

// Split out the content part of the URL
// We will need this for the matching we are about to do above
if( !preg_match( '/^([a-z][a-z](_[A-Z][A-Z])?\/)?(.*)/', $requested_url, $result ) ) {
    // This shouldn't happen...
    // But in case it does, serve a 404 and bail
    http_response_code(404);
    include("../$language/404.html");
    exit();
}

// Save our result...
$requested_page = $result[3];

// First do a local check and see if $language/$requested_page exists..
// This allows for urls such as https://docs.krita.org/user_manual/getting_started/starting_krita.html to work
if( file_exists("../$language/$requested_page") ) {
    // Then redirect them there
    header("HTTP/1.1 301 Moved Permanently");
    header("Location: /$language/$requested_page");
    exit();
}

// Go across all of our redirect rules now and see if we have any matches
foreach( $redirect_rules as $rule => $replacement ) {
    // Try to match it...
    if( !preg_match( "/$rule/", $requested_page, $result ) ) {
        // Then we need to try another one...
        continue;
    }

    // We have a winner!
    // Perform the redirect
    header("HTTP/1.1 301 Moved Permanently"); 
    header("Location: /$language/$replacement"); 
    exit();
}

// Alas it looks like we have no match :(
// Send a 404
http_response_code(404);
include("../$language/404.html");
exit();

?>
